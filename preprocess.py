from argparse import Action
from data import Data
from symbol import SymbolData, handle_options_args
from optimal import OptimalTrades
from utility import *

DATA_PARTS = ['training', 'validation', 'testing', 'evaluation']


class NeuralNetworkData(Data):

    def __init__(self, training, validation, testing, evaluation,
                 options_list, days, tolerance):
        validate_parts([training, validation, testing, evaluation])
        self.training = training
        self.validation = validation
        self.testing = testing
        self.evaluation = evaluation
        self.options_list = options_list
        self.days = days
        self.tolerance = tolerance
        super().__init__()

    def get_params(self):
        return {
            'training': self.training,
            'validation': self.validation,
            'testing': self.testing,
            'evaluation': self.evaluation,
            'options_list': self.options_list,
            'days': self.days,
            'tolerance': self.tolerance
        }

    def get_folder(self):
        return 'preprocess'

    def get_extension(self):
        return 'pkl'

    def get_base_path(self):
        return self.get_path()[:-1 - len(self.get_extension())]

    def get_part_path(self, part):
        return os.path.join(self.get_base_path(), part + '.' + self.get_extension())

    def read_data(self):
        return read_preprocess(self.get_base_path())

    def write_data(self):
        write_preprocess(self.get_base_path(), self.get_data())

    def get_new_data(self):
        log('Preprocessing neural network data...')
        return {p: self.get_new_data_part(self.get_params()[p]) for p in DATA_PARTS}

    def get_new_data_part(self, part):
        return get_data_part(part['symbols'], self.options_list, part['start'],
                             part['end'], self.days, self.tolerance)


def read_preprocess_part(path):
    try:
        data = read_pickle(path)
        return data['in'], data['out']
    except (FileNotFoundError, EOFError):
        return


def read_preprocess(path):
    data = {k: read_preprocess_part(os.path.join(path, k + '.pkl')) for k in DATA_PARTS}
    if None in data.values():
        return {}
    return data


def write_data_part(folder, data, part):
    path = os.path.join(folder, part + '.pkl')
    make_path(path)
    matrix_in, matrix_out = data[part]
    write_pickle(path, {'in': matrix_in, 'out': matrix_out})


def write_preprocess(folder, data):
    [write_data_part(folder, data, p) for p in DATA_PARTS]


def get_data_part(symbols, options_list, start, end, days, tolerance):
    matrix_in = None
    matrix_out = None
    for symbol in symbols:
        symbol_data = SymbolData(symbol, options_list).get_data()
        trades = OptimalTrades(symbol, start, end, tolerance).get_data()
        data_in, data_out = filter_incomplete(symbol_data, trades)
        data_in = add_prior_days(data_in, days, symbol_data)
        new_in = json_to_matrix(data_in)
        new_out = json_to_matrix(data_out)
        if matrix_in is None:
            matrix_in = new_in
            matrix_out = new_out
        else:
            matrix_in = np.concatenate((matrix_in, new_in))
            matrix_out = np.concatenate((matrix_out, new_out))
    return matrix_in, matrix_out


def add_prior_days(data, days, full_data):
    new_data = {}
    date_list = list(enumerate(sorted(data)))
    full_data_sorted = sorted(full_data)
    full_date_list = list(enumerate(full_data_sorted))
    start_date = full_data_sorted.index(date_list[0][1])
    end_date = full_data_sorted.index(date_list[-1][1])
    for current, date in full_date_list[start_date:end_date + 1]:
        new_data[date] = {}
        for prior in range(days + 1):
            prior_data = full_data[full_date_list[current - prior][1]]
            for col in list(prior_data):
                new_data[date][str(col) + str(prior)] = prior_data[col]
    return new_data


def validate_parts(parts):
    [validate_part(p) for p in parts]
    if False in [len(parts[0]['symbols']) == len(p['symbols']) for p in parts[1:]]:
        raise Exception('A neural network must be trained, validated, tested, '
                        'and evaluated on the same number of symbols')


def validate_part(part):
    if type(part['symbols']) is not list:
        raise Exception('symbols must be a list')
    if part['start'] is not None and type(part['start']) is not str:
        raise Exception('start must be a date string')
    if part['end'] is not None and type(part['end']) is not str:
        raise Exception('end must be a date string')


def get_part_order(args):
    order = []
    for s in args.symbol_order:
        if s.find('training') > -1:
            order += ['training']
        if s.find('validation') > -1:
            order += ['validation']
        if s.find('testing') > -1:
            order += ['testing']
        if s.find('evaluation') > -1:
            order += ['evaluation']
    return remove_duplicates(order)


def make_parts(training_symbols, validation_symbols, testing_symbols, evaluation_symbols, start, end):
    training = {
        'symbols': training_symbols,
        'start': start[0],
        'end': end[0]
    }
    validation = {
        'symbols': validation_symbols,
        'start': start[1],
        'end': end[1]
    }
    testing = {
        'symbols': testing_symbols,
        'start': start[2],
        'end': end[2]
    }
    evaluation = {
        'symbols': evaluation_symbols,
        'start': start[3],
        'end': end[3]
    }
    return training, validation, testing, evaluation


def get_parts(part_order, args):
    start = get_order_specific(args.start, part_order)
    end = get_order_specific(args.end, part_order)
    return make_parts(args.training_symbols, args.validation_symbols, args.testing_symbols,
                      args.evaluation_symbols, start, end)


def get_order_specific(l, order):
    if not len(l):
        return [None] * 4
    elif len(l) == 1:
        return [l[0]] * 4
    elif len(l) == 4:
        return (l[order.index('training')],
                l[order.index('validation')],
                l[order.index('testing')],
                l[order.index('evaluation')])
    else:
        raise Exception


def stratify_parts(symbols, percentages, start, end):
    start = to_date(start or '2002-01-01')
    end = to_date(end or Date.today().strftime('%Y-%m-%d'))
    duration = end - start
    starts = [None] * 4
    ends = [None] * 4
    starts[0] = start
    starts[1] = starts[0] + duration * percentages[0]
    starts[2] = starts[1] + duration * percentages[1]
    starts[3] = starts[2] + duration * percentages[2]
    ends[0] = starts[1]
    ends[1] = starts[2]
    ends[2] = starts[3]
    ends[3] = end
    starts = [d.strftime('%Y-%m-%d') for d in starts]
    ends = [d.strftime('%Y-%m-%d') for d in ends]
    return make_parts(symbols, symbols, symbols, symbols, starts, ends)


class SymbolAction(Action):
    def __call__(self, parser, args, values, option_string=None):
        args.symbol_order = getattr(args, 'symbol_order', []) + [self.dest]
        setattr(args, self.dest, values)


def add_args(parser):
    parser.add_argument('-s', '--symbols', type=str, nargs='+', help='symbol(s)')
    parser.add_argument('-y', '--screener', type=str, help='name of Yahoo screener')
    parser.add_argument('--percentages', type=float, nargs='+', default=[0.25, 0.25, 0.25, 0.25],
                        help='relative size of each data part')
    parser.add_argument('--training_symbols', type=str, nargs='+', action=SymbolAction,
                        help='symbol(s) to train with')
    parser.add_argument('--training_screener', type=str, action=SymbolAction,
                        help='name of Yahoo screener to train with')
    parser.add_argument('--validation_symbols', type=str, nargs='+',
                        help='symbol(s) to validate with', action=SymbolAction)
    parser.add_argument('--validation_screener', type=str, action=SymbolAction,
                        help='name of Yahoo screener to validate with')
    parser.add_argument('--testing_symbols', type=str, nargs='+', action=SymbolAction,
                        help='symbol(s) to test with')
    parser.add_argument('--testing_screener', type=str, action=SymbolAction,
                        help='name of Yahoo screener to test with')
    parser.add_argument('--evaluation_symbols', type=str, nargs='+', action=SymbolAction,
                        help='symbol(s) to evaluate with')
    parser.add_argument('--evaluation_screener', type=str, action=SymbolAction,
                        help='name of Yahoo screener to evaluate with')
    parser.add_argument('-l', '--limit', type=int,
                        help='take the first l symbols')
    parser.add_argument('--start', type=str, action='append', default=[],
                        help='start date of data')
    parser.add_argument('--end', type=str, action='append', default=[],
                        help='end date of data')
    parser.add_argument('-o', '--options', type=str, nargs='+', required=True,
                        help='indices of data_options in params.py to use')
    parser.add_argument('-t', '--tolerance', type=float, default=0.01,
                        help='tolerance to use in optimal trades algorithm')
    parser.add_argument('-d', '--days', type=int, default=0,
                        help='number of prior days of data to use as input per day')


def handle_symbols(args, parser):
    if not ((args.symbols or args.screener)
            or ((args.training_symbols or args.training_screener)
                and (args.validation_symbols or args.validation_screener)
                and (args.testing_symbols or args.testing_screener)
                and (args.evaluation_symbols or args.evaluation_screener))):
        parser.error('(-s/--symbols or -y/--screener) or '
                     '((--training_symbols or --training_screener) and '
                     '(--validation_symbols or --validation_screener) and '
                     '(--testing_symbols or --testing_screener) and'
                     '(--evaluation_symbols or --evaluation_screener)) is required')
    if args.symbols or args.screener:
        if len(args.percentages) != 4:
            parser.error('Exactly 4 --percentages required')
        elif not (0.9999 < sum(args.percentages) < 1.0001):
            parser.error('--percentages must sum to 1')
        else:
            args.symbols = get_symbols(args.symbols, args.screener, args.limit)
            if len(args.start):
                args.start = args.start[0]
                args.end = args.end[0]
            else:
                args.start = None
                args.end = None
            args.parts = stratify_parts(args.symbols, args.percentages, args.start, args.end)


def handle_dates(args, parser):
    if len(args.start) != len(args.end):
        parser.error('number of --start and --end must match')


def handle_parts(args, parser):
    if not args.symbols:
        args.training_symbols = get_symbols(args.training_symbols, args.training_screener, args.limit)
        args.evaluation_symbols = get_symbols(args.evaluation_symbols, args.evaluation_screener, args.limit)
        args.testing_symbols = get_symbols(args.testing_symbols, args.testing_screener, args.limit)
        args.evaluation_symbols = get_symbols(args.evaluation_symbols, args.evaluation_screener, args.limit)
        part_order = get_part_order(args)
        try:
            args.parts = get_parts(part_order, args)
        except:
            parser.error('Either 0, 1, or 4 --start and --end is required')


def handle_args(args, parser):
    handle_dates(args, parser)
    handle_symbols(args, parser)
    handle_parts(args, parser)
    handle_options_args(args, parser)


def main():
    args = parse_args('Preprocess neural network data.', add_args, handle_args)
    data = NeuralNetworkData(*args.parts, args.options_list, args.days, args.tolerance).get_data()
    log(data, force=args.print)
    if args.path:
        log(data.get_path(), force=args.print)


if __name__ == '__main__':
    main()
