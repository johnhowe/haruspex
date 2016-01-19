#!/bin/python2

import argparse
import csv
#import os
#import sys
import numpy as np
from parse import search, findall

def main():
    np.set_printoptions(linewidth=2048, precision=2, nanstr='', suppress=True)

    parser = argparse.ArgumentParser(description='FreeEMS Divination')
    parser.add_argument('kpa', nargs=1, help='KPA axis data')
    parser.add_argument('rpm', nargs=1, help='RPM axis data')
    parser.add_argument('ve', nargs=1, help='VE table data')
    parser.add_argument('logfile', nargs=1, help='FreeEMS datalog file')
    args = parser.parse_args()

    assert args.kpa, 'Missing KPA axis'
    assert args.rpm, 'Missing RPM axis'
    assert args.ve,  'Missing VE table'
    print
    print 'RPM axis file:', args.rpm[0]
    print 'KPA axis file:', args.kpa[0]
    print 'VE table file:', args.ve[0]
    print 'Datalog file: ', args.logfile[0]

    kpaAxis = importAxis(args.kpa[0], 'KPA')
    rpmAxis = importAxis(args.rpm[0], 'RPM')
    veTable = importTable(args.ve[0], 'VE')
    assert len(kpaAxis)*len(rpmAxis) == len(veTable), "Data sizes don't match - Incorrect table files supplied?"
    veTable = veTable.reshape(len(kpaAxis), len(rpmAxis))

#    print "ve table"
#    print veTable
#    print "rpm axis"
#    print rpmAxis
#    print "kpa axis"
#    print kpaAxis

    egoTable = egoFromLog(args.logfile[0], kpaAxis, rpmAxis)
    print egoTable

    #data log sample rate
    #friction in seconds

def importAxis(file, macroKeyword):
    axis = []
    with open(file) as f:
        for line in f:
             val = search(macroKeyword+'({:d})', line)
             if val:
                 axis.append(val[0])
    assert len(axis), "No axis data found"
    return axis

def importTable(file, macroKeyword):
    table = []
    with open(file) as f:
        for line in f:
             for val in findall(macroKeyword + '({:d})', line):
                 table.append(val[0])
    assert len(table), "No table data found"
    return np.array(table)

def isLast(itr):
    old = itr.next()
    for new in itr:
        yield False, old
        old = new
    yield True, old

def egoFromLog(file, kpaAxis, rpmAxis):
    egoTable = np.zeros([len(kpaAxis), len(rpmAxis)])
    with open(file) as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(1024))
        csvfile.seek(0)
        reader = csv.reader(csvfile, dialect, delimiter=',')

        row = reader.next()
        indexCHT = row.index("CHT")
        indexEGO = row.index("EGO")
        indexMAP = row.index("MAP")
        indexRPM = row.index("RPM")
        indexTPS = row.index("TPS")
        indexETE = row.index("ETE")

        lastTPS = 0
        datapoints = 0; ignoredEdge = 0; ignoredEGO = 0; ignoredETE = 0; ignoredDTPS=0;
        for (isLastDataPoint, row) in isLast(reader):
            datapoints += 1

            CHT  = float(row[indexCHT])
            EGO  = float(row[indexEGO])
            ETE  = float(row[indexETE])
            MAP  = float(row[indexMAP])
            RPM  = float(row[indexRPM])
            TPS  = float(row[indexTPS])
            DTPS = TPS - lastTPS
            lastTPS = TPS

            rpmCell = [j for j in rpmAxis if j >= RPM]
            kpaCell = [j for j in kpaAxis if j >= MAP]
            print rpmCell, kpaCell

    return egoTable


if __name__ == "__main__":
    main()

