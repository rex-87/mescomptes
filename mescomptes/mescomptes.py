# -*- coding: utf-8 -*-
"""
	mescomptes
	
	This project is an example of a Python project generated from cookiecutter-python.
"""

## -------- COMMAND LINE ARGUMENTS ---------------------------
## https://docs.python.org/3.7/howto/argparse.html
import argparse
CmdLineArgParser = argparse.ArgumentParser()
CmdLineArgParser.add_argument(
	"-v",
	"--verbose",
	help = "display debug messages in console",
	action = "store_true",
)
CmdLineArgs = CmdLineArgParser.parse_args()

## -------- LOGGING INITIALISATION ---------------------------
import misc
misc.MyLoggersObj.SetConsoleVerbosity(ConsoleVerbosity = {True : "DEBUG", False : "INFO"}[CmdLineArgs.verbose])
LOG, handle_retval_and_log = misc.CreateLogger(__name__)

try:
	
	## -------------------------------------------------------
	## THE MAIN PROGRAM STARTS HERE
	## -------------------------------------------------------	

    LOG.info("imports ...")

    import os
    import pandas as pd
    import datetime
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import numpy as np
    import datetime
    import copy
    # from scipy import signal

    this_file_dir = os.path.dirname(os.path.abspath(__file__))

    LOG.info("search for Lloyds csv files...")
    CsvPathList = []
    csv_dir = os.path.join(this_file_dir, r'..\raw\Lloyds') 
    for root, dirs, files in os.walk(csv_dir):
        for name in files:
            if ".csv" in name:
                CsvPathList.append(os.path.join(root, name))

    # merge Lloyds csv files
    LOG.info("merge Lloyds csv files...")
    MergedLloydsCsvPath = os.path.join(this_file_dir, r'..\proc\Lloyds_merged.csv')
    with open(MergedLloydsCsvPath, 'w') as fout:
        
        # copy csv files removing repeted lines
        UniqueLineList = []
        for CsvPath in CsvPathList:
            
            with open(CsvPath, 'r') as fin:
                fin_lines = fin.readlines()
            
            # for each input file line
            for fin_line in fin_lines:
                if fin_line in UniqueLineList:
                    # line was already present in another file, ignore
                    continue
                else:
                    # This line is unique, save it ...
                    UniqueLineList.append(fin_line) 
                    # ... and copy it to the output file
                    fout.write(fin_line)

    LOG.info("read merged lloyds csv...")
    MergedLloydsDf = pd.read_csv(MergedLloydsCsvPath)

    LOG.info("append timestamp column...")
    TimestampDf = pd.DataFrame(
        { 'Timestamp' : [ datetime.datetime.strptime(DateStr, "%d/%m/%Y").timestamp() for DateStr in MergedLloydsDf['Transaction Date']] },
    )
    MergedLloydsDf = MergedLloydsDf.join(TimestampDf)
    MergedLloydsDf = MergedLloydsDf.sort_values(by = 'Timestamp') 

    fromtimestamp = datetime.datetime.fromtimestamp
    dateconv = np.vectorize(fromtimestamp)
    
    LOG.info("remove transfers to ISA...")
    df = MergedLloydsDf[~MergedLloydsDf['Transaction Description'].str.contains('R THIBAULT')].sort_values(by = 'Timestamp')
    df = df[~df['Transaction Description'].str.contains('TO 77490187689860')].sort_values(by = 'Timestamp') # (£1 paid to ISA account)
    
    lloyds_current_balance = list(MergedLloydsDf['Balance'])[-1]
    # df = MergedLloydsDf.sort_values(by = 'Timestamp')                                            

    LOG.info("sum transactions which occurred on the same day...")
    df = df.groupby(['Timestamp'], as_index = False).sum()

    LOG.info("populate missing days...")
    timestamp_dr = pd.date_range(fromtimestamp(df['Timestamp'].iloc[0]), fromtimestamp(df['Timestamp'].iloc[-1]))
    df.index = dateconv(df['Timestamp'])
    df = df.reindex(timestamp_dr, fill_value=0)

    LOG.info("calculate rolling averages...")
    
    def GetSavingsDelta(deb, cre):
        return cre - deb

    df['Savings Delta'] = GetSavingsDelta(df['Debit Amount'].fillna(0), df['Credit Amount'].fillna(0))
    df['Savings'] = np.cumsum(df['Savings Delta'])
    d1m = 31;  df['Savings 1m'] = df['Savings'].rolling(d1m, center = True).mean()
    d3m = 91;  df['Savings 3m'] = df['Savings'].rolling(d3m, center = True).mean()
    d1y = 365; df['Savings 1y'] = df['Savings'].rolling(d1y, center = True).mean();
    # b, a = signal.butter(2, 0.004)
    # df['Savings Butterworth'] = signal.filtfilt(b, a, df['Savings'], padlen = 600)
    # df['Savings Butterworth'] = signal.lfilter(b, a, df['Savings'])
    lloyds_total_savings = list(df['Savings'])[-1]
    isa_balance = lloyds_total_savings - lloyds_current_balance
    
    CIC_courant_df = pd.read_csv(os.path.join(this_file_dir, r'..\raw\CIC\cic_courant.csv'))
    CIC_livretA_df = pd.read_csv(os.path.join(this_file_dir, r'..\raw\CIC\cic_livretA.csv'))
    def get_eur_balance(eur_df):
        
        bal_eur = eur_df.iloc[-1]['Balance']
        bal_gbp = int(eur_df.iloc[-1]['Balance']*100/eur_df.iloc[-1]['gbp/eur rate'])/100
        
        return bal_eur, bal_gbp, eur_df.iloc[-1]['gbp/eur rate']
    cic_courant_eur, cic_courant_gbp, gbp_eur_rate = get_eur_balance(CIC_courant_df)
    cic_livretA_eur, cic_livretA_gbp, gbp_eur_rate = get_eur_balance(CIC_livretA_df)
    
    LOG.info("LLoyds: £{:.2f} (£{:.2f} + £{:.2f} = {:.2f}€)".format(lloyds_total_savings, lloyds_current_balance, isa_balance, lloyds_total_savings*gbp_eur_rate))
    LOG.info("CIC: {:.2f}€ ({:.2f}€ + {:.2f}€) = £{:.2f}".format(cic_courant_eur+cic_livretA_eur, cic_courant_eur, cic_livretA_eur, cic_courant_gbp+cic_livretA_gbp))
    LOG.info("Total: £{:.2f} = {:.2f}€)".format(lloyds_total_savings+cic_courant_gbp+cic_livretA_gbp, cic_courant_eur+cic_livretA_eur+lloyds_total_savings*gbp_eur_rate))

    LOG.info("save processed lloyds csv...")
    ProcLloydsCsvPath = os.path.join(this_file_dir, r'..\proc\Lloyds_proc.csv')
    df.to_csv(path_or_buf = ProcLloydsCsvPath)

    LOG.info("PLOT...")
    plt.plot_date(df.index, df['Savings'], 'k.', markersize = 1,)
    plt.plot_date(df.index, df['Savings 1m'], 'y-')
    plt.plot_date(df.index, df['Savings 3m'], 'g-')
    plt.plot_date(df.index, df['Savings 1y'], 'b-')
    # plt.plot_date(df.index, df['Savings Butterworth'], 'r-')
    plt.gca().xaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator(12))
    plt.gca().yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator(5))
    plt.grid()
    plt.grid(which = 'minor', linestyle = '--', alpha = 0.5)
    plt.gcf().set_dpi(100)
    plt.show()

    plt.plot_date(df.index, df['Savings'].diff(), 'k.', markersize = 1,)
    plt.plot_date(df.index, df['Savings 1m'].diff(), 'y-')
    plt.plot_date(df.index, df['Savings 3m'].diff(), 'g-')
    plt.plot_date(df.index, df['Savings 1y'].diff(), 'b-')
    # plt.plot_date(df.index, df['Savings Butterworth'].diff(), 'r-')
    plt.gca().xaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator(12))
    plt.gca().yaxis.set_minor_locator(matplotlib.ticker.AutoMinorLocator(5))
    plt.grid()
    plt.grid(which = 'minor', linestyle = '--', alpha = 0.5)
    plt.gcf().set_dpi(100)
    plt.show()

## -------- SOMETHING WENT WRONG -----------------------------	
except:

	import traceback
	LOG.error("Something went wrong! Exception details:\n{}".format(traceback.format_exc()))

## -------- GIVE THE USER A CHANCE TO READ MESSAGES-----------
finally:
	
	pass
    # input("Press any key to exit ...")
