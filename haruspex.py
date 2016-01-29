#!/bin/python2

import matplotlib as mpl
mpl.use("Agg")
import argparse
import csv
import numpy as np
import os
#import sys
import seaborn as sns
from parse import search, findall
import matplotlib.pyplot as plt

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

    #os.system('clear')
    egoTable, egoTableWeight = egoFromLog(args.logfile[0], kpaAxis, rpmAxis, veTable)
    # TODO Check that we got something back - eg, perhaps we never got to operating temperature
    print "rpmAxis ", rpmAxis
    print "kpaAxis ", kpaAxis
    print "veTable\n", veTable
    print "egoTableWeight\n", egoTableWeight
    print "egoTable\n", egoTable

    plt.title("Measured Lambda")
    sns.heatmap(egoTable, annot=True, fmt='.2f', linewidths=0.01, vmin=0.7, vmax=1.3, center=1.0,  \
                xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('ego.png')

    plt.clf()
    plt.title("Measured Lambda Confidence")
    sns.heatmap(egoTableWeight, linewidths=.1, \
                xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('egoConf.png')


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

def getCellWeight(xAxis, yAxis, xIndex, yIndex):
    weight = np.zeros([len(yAxis), len(xAxis)])
    x0 = next((j for j in reversed(xAxis) if j <= xIndex), xAxis[0])
    x1  = next((j for j in xAxis if j >= xIndex), xAxis[-1])
    y0 = next(( j for j in reversed(yAxis) if j <= yIndex), yAxis[0])
    y1  = next((j for j in yAxis if j >= yIndex), yAxis[-1])

    if (x0 == x1) and (y0 == y1):
        weight[yAxis.index(y0), xAxis.index(x0)] = 1
    elif (x0 == x1):
        weight[yAxis.index(y0), xAxis.index(x0)] = (y1 - yIndex) / (y1 - y0)
        weight[yAxis.index(y1), xAxis.index(x0)] = (yIndex - y0) / (y1 - y0)
    elif (y0 == y1):
        weight[yAxis.index(y0), xAxis.index(x0)] = (x1 - xIndex) / (x1 - x0)
        weight[yAxis.index(y0), xAxis.index(x1)] = (xIndex - x0) / (x1 - x0)
    else:
        area_00 = (yIndex - y0) * (xIndex - x0)
        area_01 = (yIndex - y0) * (x1 - xIndex)
        area_10 = (y1 - yIndex) * (xIndex - x0)
        area_11 = (y1 - yIndex) * (x1 - xIndex)
        area = area_00 + area_01 + area_10 + area_11

        weight[yAxis.index(y0), xAxis.index(x0)] = area_11 / area
        weight[yAxis.index(y0), xAxis.index(x1)] = area_10 / area
        weight[yAxis.index(y1), xAxis.index(x0)] = area_01 / area
        weight[yAxis.index(y1), xAxis.index(x1)] = area_00 / area

    return weight

def egoFromLog(file, kpaAxis, rpmAxis, veTable):
    xx, yy = np.meshgrid(rpmAxis, kpaAxis)
    lambdaSigmaNum = np.zeros([len(kpaAxis), len(rpmAxis)])
    lambdaSigmaDen = np.zeros([len(kpaAxis), len(rpmAxis)])
    with open(file) as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(1024))
        csvfile.seek(0)
        reader = csv.reader(csvfile, dialect, delimiter=',')

        row = reader.next()
        #indexCHT = row.index("CHT")
        indexEGO = row.index("EGO")
        indexMAP = row.index("MAP")
        indexRPM = row.index("RPM")
        indexTPS = row.index("TPS")
        indexETE = row.index("ETE")

        lastTPS = 0
        datapoints = 0;
        ignoredEGO = 0; ignoredETE = 0; ignoredDTPS=0;

        for (isLastDataPoint, row) in isLast(reader):
            datapoints += 1

            #CHT  = float(row[indexCHT])
            EGO  = float(row[indexEGO])
            ETE  = float(row[indexETE])
            MAP  = float(row[indexMAP])
            RPM  = float(row[indexRPM])
            TPS  = float(row[indexTPS])
            DTPS = TPS - lastTPS
            lastTPS = TPS

            if (ETE > 100.1):
                ignoredETE += 1
                continue
            if (EGO > 1.4) or (EGO < 0.6):
                ignoredEGO += 1
                continue
            if (DTPS > 0.01):
                ignoredDTPS += 1
                continue
            cellWeight = getCellWeight(rpmAxis, kpaAxis, RPM, MAP)
            lambdaSigmaNum += cellWeight * EGO
            lambdaSigmaDen += cellWeight
            #import ipdb;ipdb.set_trace() # SET PDB BREAKPOINT

    print datapoints, "samples seen; ignored", ignoredETE, "warmup, ", ignoredEGO, "ego, and", ignoredDTPS, "dtps"

    print "lambdaSigmaNum\n", lambdaSigmaNum
    print "lambdaSigmaDen\n", lambdaSigmaDen
    return lambdaSigmaNum/lambdaSigmaDen, lambdaSigmaDen


if __name__ == "__main__":
    main()

