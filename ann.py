import pickle
from argparse import ArgumentParser, Action
from data import Data
from symbol import SymbolData
from optimal import OptimalTrades
from utility import *


class NeuralNetwork(Data):

    def __init__(self, training=None, validation=None, testing=None):
        self.training = training
        self.validation = validation
        self.testing = testing
        super().__init__()


class NeuralNetworkData(Data):

    def __init__(self, training, validation, testing, evaluation,
                 options_list, days, tolerance):
        [validate_part(p) for p in [training, validation, testing, evaluation]]
        self.training = training
        self.validation = validation
        self.testing = testing
        self.evaluation = evaluation
        if not (len(training['symbols']) == len(validation['symbols'])
                == len(testing['symbols']) == len(evaluation['symbols'])):
            raise Exception('A neural network must be trained, validated, tested, '
                            'and evaluated on the same number of symbols')
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
        return 'ann'

    def get_extension(self):
        return 'pkl'

    def get_part_path(self, part):
        ext = self.get_extension()
        return self.get_path()[:-1 - len(ext)] + '.' + ext

    def read_data(self):
        data = {
            'training': self.read_data_part('training'),
            'validation': self.read_data_part('validation'),
            'testing': self.read_data_part('testing'),
            'evaluation': self.read_data_part('evaluation')
        }
        if None in data.values():
            return {}
        return data

    def read_data_part(self, part):
        try:
            with open(self.get_part_path(part), 'rb') as fh:
                data = pickle.loads(fh.read())
                return data['in'], data['out']
        except (FileNotFoundError, EOFError) as e:
            return

    def write_data(self):
        data = self.get_data()
        self.write_data_part(data, 'training')
        self.write_data_part(data, 'validation')
        self.write_data_part(data, 'testing')
        self.write_data_part(data, 'evaluation')

    def write_data_part(self, data, part):
        with open(self.get_part_path(part), 'wb') as fh:
            matrix_in, matrix_out = data[part]
            fh.write(pickle.dumps({'in': matrix_in, 'out': matrix_out}))

    def get_new_data(self):
        log('Preprocessing neural network data...')
        return {
            'training': self.get_new_data_part(self.training),
            'validation': self.get_new_data_part(self.validation),
            'testing': self.get_new_data_part(self.testing),
            'evaluation': self.get_new_data_part(self.evaluation)
        }

    def get_new_data_part(self, part):
        matrix_in = None
        matrix_out = None
        for symbol in part['symbols']:
            symbol_data = SymbolData(symbol, self.options_list).get_data()
            trades = OptimalTrades(symbol, part['start'], part['end'], self.tolerance).get_data()
            data_in, data_out = filter_incomplete(symbol_data, trades)
            data_in = add_prior_days(data_in, self.days, symbol_data)
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


def validate_part(part):
    if type(part['symbols']) is not list:
        raise Exception('symbols must be a list')
    if part['start'] is not None and type(part['start']) is not str:
        raise Exception('start must be a date string')
    if part['end'] is not None and type(part['end']) is not str:
        raise Exception('end must be a date string')


class SymbolAction(Action):
    def __call__(self, parser, args, values, option_string=None):
        args.symbol_order = getattr(args, 'symbol_order', []) + [self.dest]
        setattr(args, self.dest, values)


def parse_args():
    parser = ArgumentParser(description='Load a neural network.')
    parser.add_argument('-s', '--symbols', type=str, nargs='+',
                        help='symbol(s) to train, validate, and test with')
    parser.add_argument('-y', '--screener', type=str,
                        help='name of Yahoo screener to train, validate, and test with')
    parser.add_argument('-b', '--buckets', type=int, default=1,
                        help='stratify data into b buckets')
    parser.add_argument('--percentages', type=float, nargs='+',
                        help='stratify data into b buckets')
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
    parser.add_argument('-t', '--tolerance', type=float, required=True,
                        help='tolerance to use in optimal trades algorithm')
    parser.add_argument('-d', '--days', type=int, default=0,
                        help='number of prior days of data to use as input per day')
    parser.add_argument('-p', '--print', action='store_true', help='print the data')
    parser.add_argument('-v', '--verbose', action='store_true', help='log debug messages')

    args = parser.parse_args()

    set_verbosity(args.verbose)

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

    if len(args.start) != len(args.end):
        parser.error('number of --start and --end must match')
    elif args.symbols or args.screener:
        if not args.percentages:
            parser.error('--percentages is required with -s/--symbols or -y/--screener')
        elif len(args.percentages) != 4:
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
    else:
        args.training_symbols = get_symbols(args.training_symbols, args.training_screener, args.limit)
        args.evaluation_symbols = get_symbols(args.evaluation_symbols, args.evaluation_screener, args.limit)
        args.testing_symbols = get_symbols(args.testing_symbols, args.testing_screener, args.limit)
        args.evaluation_symbols = get_symbols(args.evaluation_symbols, args.evaluation_screener, args.limit)
        part_order = get_part_order(args)
        try:
            args.training, args.validation, args.testing, args.evaluation = get_parts(part_order, args)
        except:
            parser.error('Either 0, 1, or 4 --start and --end is required')

    return args


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


def stratify_parts(symbols, buckets, percentages, start, end):
    start = to_date(start or '2002-01-01')
    end = to_date(end or date.today().strftime('%Y-%m-%d'))
    duration = end - start
    starts = [0] * 4
    ends = [0] * 4
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


def main():
    args = parse_args()
    options_list = get_options_list(args.options)
    data = None
    if args.symbols:
        parts = stratify_parts(args.symbols, args.buckets, args.percentages, args.start, args.end)
        data = NeuralNetworkData(*parts, options_list, args.days, args.tolerance).get_data()
    else:
        data = NeuralNetworkData(args.training, args.validation, args.testing, args.evaluation,
                                 options_list, args.days, args.tolerance).get_data()
    if args.print:
        log(data, force=True)


if __name__ == '__main__':
    main()