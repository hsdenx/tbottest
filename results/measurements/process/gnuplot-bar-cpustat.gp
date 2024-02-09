# variables
# datafile -> filename of input file
# outputfile -> filename of output file
# columcount -> count of columns

set xlabel "Loop"
set ylabel "CPU usage in %"
set boxwidth 0.75 absolute
set style fill   solid 1.00 border lt -1
set key outside right top vertical Left reverse noenhanced autotitles columnhead nobox
set key invert samplen 4 spacing 1 width 0 height 0
set style histogram rowstacked title  offset character 0, 0, 0
set datafile missing '-'
set style data histograms
set xtics border in scale 0,0 nomirror offset character 0, 0, 0 autojustify
set xtics  norangelimit font "arial,20"
set xtics autofreq
set title "process usage"

set yrange [0:100]
set grid ytics
set terminal png enhanced size 2048,768
set termoption noenhanced
set output outputfile

i = 2
plot datafile using 2:xtic(1), for [i=3:columcount-3] '' using i, \
     datafile using "cpu_user":xtic(1) w lp, \
     datafile using "cpu_system":xtic(1) w lp, \
     datafile using "cpu_complete":xtic(1) w lp, \
