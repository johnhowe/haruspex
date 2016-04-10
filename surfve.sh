#!/bin/bash

grep VE /home/john/git/freeems-vanilla/src/main/data/tables/ve/JohnsAE86VE.h | sed 's/), VE(/\ /g' | sed -r 's/ *VE\(//g' | sed -r 's/\),.*$//g' | tee /tmp/ve
grep KPA /home/john/git/freeems-vanilla/src/main/data/tables/axis/JohnsAE86-KPALoad.h | sed -r 's/ *KPA\(//' | sed -r 's/\),?//' | tee /tmp/kpa
grep RPM /home/john/git/freeems-vanilla/src/main/data/tables/axis/JohnsAE86-RPM.h | sed -r 's/ *RPM\(//' | sed -r 's/\),?//' | tee /tmp/rpm

./surfve.m /tmp/ve /tmp/kpa /tmp/rpm




