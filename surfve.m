#!/bin/octave-cli -q

arg_list = argv();
ve = load(arg_list{1});
kpa = load(arg_list{2});
rpm = load(arg_list{3});
[X, Y] = meshgrid(rpm, kpa)
whos
surf(X, Y, ve)
pause

