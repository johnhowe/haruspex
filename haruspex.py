#!/bin/python2
#import ipdb;ipdb.set_trace() # SET PDB BREAKPOINT

import matplotlib as mpl
mpl.use("Agg")
import argparse
import csv
import numpy as np
#import os
import sys
import seaborn as sns
from parse import search, findall
import matplotlib.pyplot as plt

# TODO VE change friction table - can add blacklisting for -ve value?
# TODO Get paths from a config file - perhaps log is passed explicitly still
# TODO Lambda distribution per cell - store which edges were being interpolated against
# TODO Highlight engine issues eg IAT heat soak ;)
# TODO Output to ve header file with specific changes in comments fields
# TODO Summary of changes - modified cells, log length, etc.
# TODO Plot of KPA/RPM distributions
# TODO Export CSV with analysis info stamped in
# TODO Pass in multiple logs

minConfidenceThreshold = 100
maxETE = 100.1
maxEGO = 1.4
minEGO = 0.6
minRPM = 100
maxDTPS = 0.01
stoichiometricAFRPetrol = 14.7
veChangeFriction = 1000
sampleRejectionWindowWidth = 30

def main():
    np.set_printoptions(linewidth=2048, precision=2, nanstr='', suppress=True)

    parser = argparse.ArgumentParser(description='FreeEMS Divination')
    parser.add_argument('kpa', nargs=1, help='KPA axis data')
    parser.add_argument('rpm', nargs=1, help='RPM axis data')
    parser.add_argument('ve', nargs=1, help='VE table data')
    parser.add_argument('afr', nargs=1, help='AFR table data')
    parser.add_argument('logfile', nargs=1, help='FreeEMS datalog file')
    args = parser.parse_args()

    assert args.kpa, 'Missing KPA axis'
    assert args.rpm, 'Missing RPM axis'
    assert args.ve,  'Missing VE table'

    print '\nRPM axis file:', args.rpm[0]
    print 'KPA axis file:', args.kpa[0]
    print 'VE table file:', args.ve[0]
    print 'AFR table file:', args.afr[0]
    print 'Datalog file: ', args.logfile[0]

    kpaAxis = importAxis(args.kpa[0], 'KPA')
    rpmAxis = importAxis(args.rpm[0], 'RPM')
    veTable = importTable(args.ve[0], 'VE')
    assert len(kpaAxis)*len(rpmAxis) == len(veTable), "Axis don't fit VE table - Incorrect table files supplied?"
    veTable = veTable.reshape(len(kpaAxis), len(rpmAxis))
    afrTable = importTable(args.afr[0], 'AP')
    assert len(kpaAxis)*len(rpmAxis) == len(afrTable), "Axis don't fit AFR table - For now the AFR table must be the same dimensions as the VE table"
    afrTable = afrTable.reshape(len(kpaAxis), len(rpmAxis))
    if (np.min(afrTable) > 3): # convert from AFR to Lambda
        afrTable = afrTable / stoichiometricAFRPetrol

    egoTable, confidenceTable = egoFromLog(args.logfile[0], kpaAxis, rpmAxis, veTable)
    if (sum(sum(confidenceTable)) == 0):
        print "No valid data - perhaps we never go to operating temperature"
        return

    newVeTable = fixVE(veTable, afrTable, egoTable, confidenceTable)
    print "\nProphesied VE table:"
    dumpTable(newVeTable, 'VE')

    plt.clf()
    plt.title("VE Table")
    sns.heatmap(veTable , annot=True, fmt='.1f', \
                xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('ve.png')

    plt.clf()
    plt.title("Target Lambda")
    sns.heatmap(afrTable , annot=True, fmt='.2f', \
                xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('afr.png')

    plt.clf()
    plt.title("Measured EGO")
    sns.heatmap(egoTable, annot=True, fmt='.2f', vmin=0.7, vmax=1.3, \
                xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('ego.png')

    plt.clf()
    plt.title("Confidence")
    sns.heatmap(confidenceTable,  vmin=minConfidenceThreshold, \
                annot=True, fmt='.0f', xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('egoConf.png')

    plt.clf()
    plt.title("Prophesied VE Table")
    sns.heatmap(newVeTable , annot=True, fmt='.1f', \
                xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('newVe.png')

    plt.clf()
    plt.title("Delta VE Table")
    sns.heatmap(newVeTable - veTable , annot=True, fmt='.1f', \
                xticklabels=rpmAxis, yticklabels=kpaAxis)
    plt.savefig('deltaVe.png')

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
            for val in findall(macroKeyword + '({:g})', line):
                 table.append(val[0])
    assert len(table), "No table data found"
    return np.array(table)

def dumpTable(table, macroKeyword):
    for index, value in np.ndenumerate(table):
        if (index[1] == 0):
            sys.stdout.write("\n")
        sys.stdout.write(" {0}({1:.1f}),".format(macroKeyword, value))
    sys.stdout.write("\n")

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

        lastTPS = sample = ignoredEGO = ignoredRPM = ignoredETE = ignoredDTPS = 0;

        rejectedSamples = np.array([])
        sys.stdout.write("Parsing datalog")
        for (isLastDataPoint, row) in isLast(reader):
            sample += 1
            if (sample % 5000 == 0):
                sys.stdout.write('.')
                sys.stdout.flush()

            #CHT  = float(row[indexCHT])
            EGO  = float(row[indexEGO])
            ETE  = float(row[indexETE])
            MAP  = float(row[indexMAP])
            RPM  = float(row[indexRPM])
            TPS  = float(row[indexTPS])
            DTPS = TPS - lastTPS
            lastTPS = TPS
            if (RPM < minRPM):
                ignoredRPM += 1
            elif (ETE > maxETE):
                ignoredETE += 1
            elif (EGO > maxEGO) or (EGO < minEGO):
                ignoredEGO += 1
            elif (DTPS > maxDTPS):
                ignoredDTPS += 1
            else:
                # the sample is accepted
                continue
            rejectedSamples = np.append(rejectedSamples, sample)

        rejectedSamples = np.append(rejectedSamples, sample)
        csvfile.seek(0)
        row = reader.next()
        sample = 0
        nextRejectedSampleIndex = 0
        numRejectedSamples = 0
        for (isLastDataPoint, row) in isLast(reader):
            sample += 1
            if (sample % 5000 == 0):
                sys.stdout.write('\b \b')
                sys.stdout.flush()

            if (sample > rejectedSamples[nextRejectedSampleIndex] + sampleRejectionWindowWidth/2):
                nextRejectedSampleIndex += 1
            if (abs(sample - rejectedSamples[nextRejectedSampleIndex]) <= sampleRejectionWindowWidth/2):
                numRejectedSamples += 1
                continue

            #CHT  = float(row[indexCHT])
            EGO  = float(row[indexEGO])
            ETE  = float(row[indexETE])
            MAP  = float(row[indexMAP])
            RPM  = float(row[indexRPM])
            TPS  = float(row[indexTPS])
            DTPS = TPS - lastTPS
            lastTPS = TPS

            cellWeight = getCellWeight(rpmAxis, kpaAxis, RPM, MAP)
            lambdaSigmaNum += cellWeight * EGO
            lambdaSigmaDen += cellWeight

    print '\n', sample, "samples seen; ignored", ignoredETE, "warmup,", ignoredRPM, "rpm,", ignoredEGO, "ego, and", ignoredDTPS, "dtps"
    print rejectedSamples.size, 'samples rejected'
    print numRejectedSamples, 'samples rejected including window'

    #print "lambdaSigmaNum\n", lambdaSigmaNum
    #print "lambdaSigmaDen\n", lambdaSigmaDen
    return lambdaSigmaNum/lambdaSigmaDen, lambdaSigmaDen


def fixVE(veTable, afrTable, egoTable, confidenceTable):
    newVeTable = np.zeros_like(veTable)
    for index, value in np.ndenumerate(veTable):
        effectiveLambda = (veChangeFriction * afrTable[index] + egoTable[index] * confidenceTable[index]) / (veChangeFriction + confidenceTable[index])
        #TODO plot the effectiveLambda table too
        if (effectiveLambda > 0):
            newVeTable[index] = veTable[index] * (effectiveLambda / afrTable[index])
        else:
            newVeTable[index] = veTable[index]
    return newVeTable

if __name__ == "__main__":
    main()

