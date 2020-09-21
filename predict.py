#!/usr/bin/python3
import argparse
from joblib import dump, load
import utils
from sklearn.metrics import recall_score, precision_score, accuracy_score
import sys
import re


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", help='the file to be predict.')
    parser.add_argument("--saved_models", required=True, nargs='+', help='the trained models used for prediction.')
    parser.add_argument("--asm_source", required=True, help='the file that generated by llvm-objdump -d.')
    parser.add_argument("--marked_asm", required=True, help='the asm file with marking prediction.')
    return parser.parse_args()


def xy(data_set):
    Y = data_set['target']
    X = data_set.drop(columns=['module name', 'address', 'target'])
    if 'index' in X:
        X.drop(columns=['index'], inplace=True)
    return X, Y


def predict(model, data, X, Y):
    dc = load(model)
    y_predict = dc.predict(X)
    acc = accuracy_score(Y, y_predict)
    precision = precision_score(Y, y_predict)
    recall = recall_score(Y, y_predict)
    print('A:R:P = %f:%f:%f' % (acc, recall, precision))
    # sys.exit(0)
    errors = {}
    for i in range(0, len(data)):
        addr = data.iloc[i,1]
        addr_dec = int(addr, 16)
        target = data.iloc[i,2]
        if target == 1 or y_predict[i] == 1:
            if target == y_predict[i]:
                continue
            elif target > y_predict[i]:
                errors[addr_dec] = 'FN'
            else:
                errors[addr_dec] = 'FP'
        else:
            continue
        print("Address: %s, Error: %s" % (addr, errors[addr_dec]))
    return y_predict


def add_prediction(summary, round):
    for i in range(len(summary)):
        summary[i] += round[i]


def is_func_header(line):
    header_pattern = re.compile('^[0-9a-f]* <[_\\.0-9a-zA-Z]*>:$')
    match = header_pattern.fullmatch(line)
    if match:
        # print('match header: %s' % line)
        return True
    else:
        return False


def is_func_body(line):
    body_pattern = re.compile('^   [0-9a-f]*: [0-9a-f][0-9a-f] .*')
    match = body_pattern.fullmatch(line)
    if match:
        # print('match body: %s' % line)
        return True
    else:
        return False


def check_line(line, errors):
    if line.endswith('\n'):
        line = line[:-1]
    if is_func_header(line):
        addr = int(line.split(' ')[0], 16)
        # print('header address in int: %d' % addr)
        if addr in errors:
            line = line + ' #<' + errors[addr] + ">"
            print(line)
    elif is_func_body(line):
        addr = int(line[3:].split(':')[0], 16)
        # print('body address in int: %d' % addr)
        if addr in errors and errors[addr] == 'FP':
            line = line + ' #<' + errors[addr] + ">"
            print(line)
    return line


def mark_errors(asm_source, errors, asm_out):
    output_lines = []
    with open(asm_source, 'r') as infile:
        for line in infile:
            new_line = check_line(line, errors)
            output_lines.append(new_line)
    with open(asm_out, 'w') as outfile:
        outfile.write('\n'.join(output_lines))


def predict_summary(sum_prediction, data, threshold):
    summary = {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}
    errors = {}
    for i in range(0, len(data)):
        addr = data.iloc[i,1]
        addr_dec = int(addr, 16)
        target = data.iloc[i,2]
        if target == 1 or sum_prediction[i] == threshold:
            if target == 1 and sum_prediction[i] == threshold:
                summary['TP'] += 1
            elif target == 1:
                errors[addr_dec] = 'FN'
                summary['FN'] += 1
                print("Address: %s, Error: %s" % (addr, errors[addr_dec]))
            else:
                errors[addr_dec] = 'FP'
                summary['FP'] += 1
                print("Address: %s, Error: %s" % (addr, errors[addr_dec]))
        else:
            summary['TN'] += 1
    acc = float(summary['TP'] + summary['TN']) / float(len(data))
    recall = float(summary['TP']) / float(summary['TP'] + summary['FN'])
    precision = float(summary['TP']) / float(summary['TP'] + summary['FP'])
    print('A:R:P = %f:%f:%f' % (acc, recall, precision))
    print(errors)
    return errors    


def main():
    args = get_args()
    data = utils.toDf(args.input_file)
    sum_prediction = []
    X, Y = xy(data)
    for model in args.saved_models:
        print('##### predict with model: %s ########' % model)
        round_prediction = predict(model, data, X, Y)
        if len(sum_prediction) == 0:
            sum_prediction = round_prediction
        else:
            add_prediction(sum_prediction, round_prediction)
    print('##### start summary: ########')
    errors = predict_summary(sum_prediction, data, len(args.saved_models))
    mark_errors(args.asm_source, errors, args.marked_asm)


if __name__ == '__main__':
    main()