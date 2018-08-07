import numpy as np
import pandas as pd
import couchdb
import matplotlib.pyplot as plt
from scipy.stats import norm
from eeg import getTrialNumList, plotDataSubset

def getBehaviorDataSession(dbAddress, dbName, sessionNum):
    """
    Fetch behavior data from couchdb (SOA, SNR and trial duration).

    Parameters
    ----------
    dbAddress : str
        Path to the couch database.
    dbName : str
        Name of the database on the couch instance.
    sessionNum : int
        Behavior data will be fetched from this sessionNum.

    Returns
    -------
    allDoc : instance of pandas.core.DataFrame
        A dataframe containing requested data.
    """

    couch = couchdb.Server(dbAddress)
    db = couch[dbName]

    count = 0
    alldoc = []
    for doc in db.view('_all_docs'):
        if (doc['id'].startswith('maskingEEG_%d' % sessionNum)):
            alldoc.append(db.get(doc['id']))

    alldoc = pd.DataFrame(alldoc)
    alldoc = alldoc.sort_values(['time']).reset_index(drop=True)
    return alldoc

def getBehaviorData(dbName, sessionNums):
    """
    Get behavior data from the couch database according to the name of the DB and
    the sessions.

    Parameters
    ----------
    dbName : str
        Name of the database on the couch instance.
    sessionNums : array-like
        List of sessions to keep.

    Returns
    -------
    behaviorData : instance of pandas.core.DataFrame
        Dataframe containing all parameters of all trials.
    """
    password = "a"
    dbAddress = "https://db.auditory.fr:6984/"
    dbAddressLog = "https://%s:%s@db.auditory.fr:6984/" % (dbName, password)

    behaviorData = []
    for session in sessionNums:
        print 'loading session', session
        behaviorData.append(getBehaviorDataSession(dbAddress=dbAddressLog,
                               dbName=dbName,
                               sessionNum=session))

    behaviorData = pd.concat(behaviorData)
    behaviorData.trialNum = np.arange(behaviorData.shape[0])
    behaviorData = behaviorData.reset_index()
    return behaviorData

def analyses(data, verbose):
    """
    Evaluate the behavior data by computing hits rate and false alarm rates. The
    continuous responses given by the participant are compared to the time stamps
    of the gaps in the attended stream and also in the unattended (if there is
    one). For each response: 1.calculate the delay between this response and each
    attended gap (`lagCorrect`). 2. calculate the delay between this response
    and each unattended gap (`laginCorrect`). 3. keep only positive values in
    each array because the response is done after the gap. This removes all
    other gaps for this response. 4. take the smaller value in each
    array: `minCorrect` and `minIncorrect`. 5. we consider that the response
    is linked to the gap if the delay is between `minThresh` and `maxThresh`.
    The margins should avoid having bumps in the two streams separated by less
    than maxThresh - minThresh.

    Parameters
    ----------
    data : instance of pandas.core.DataFrame
        Behavior data to use to run the analyses.
    verbose : bool
        Print more details about the process.

    Returns
    -------
    analyses : instance of pandas.core.DataFrame
        Dataframe containing the number of hits and false alarms for each trial.
    """
    allHitTime = []
    allFalseHitTime = []

    # we don't expect reaction time bellow minThresh
    minThresh = 0.3
    maxThresh = 1

    analyses = pd.DataFrame(columns=['trial', 'freqDiff', 'hit', 'hit1', 'FA',
        'FA1', 'falseHit', 'allFA', 'dprime', 'TC', 'correctStream', 'twoStreams';
        'gapNum'])
    trial = 0
    for i in data.trialNum:
        # get subset of data corresponding to the current trial
        dataTrial = data[data.trialNum==trial]

        if verbose:
            print '\n\ntrial %s' % trial
            print 'Freq diff: %d' % dataTrial.freqDiff

        gapNum = dataTrial.bumpNumber.values[0]

        if (data['correctStream'][trial]):
            correctGap = np.array(dataTrial.delayBump1.values[0])
            incorrectGap = np.array(dataTrial.delayBump0.values[0])
        else:
            correctGap = np.array(dataTrial.delayBump0.values[0])
            incorrectGap = np.array(dataTrial.delayBump1.values[0])
        resp = np.array(dataTrial.continuousResponses.values[0])

        hit = 0.
        FA = 0.
        miss = 0.
        falseHit = 0.
        falseHitTime = []
        hitTime = []
        FATime = []
        for i in resp:
            if not np.isnan(i):
                if verbose:
                    print 'response: ', i
                lagCorrect = i-correctGap
                lagIncorrect = i-incorrectGap
                # response are made after gap: keep only positive values
                lagCorrect = lagCorrect[lagCorrect>0]
                lagIncorrect = lagIncorrect[lagIncorrect>0]

                isCorrectExists = lagCorrect.shape[0] > 0
                isIncorrectExists = lagIncorrect.shape[0] > 0

                if isCorrectExists:
                    minCorrect = np.min(lagCorrect)
                    if verbose:
                        print 'min distance with correct = ', minCorrect
                if isIncorrectExists:
                    minIncorrect = np.min(lagIncorrect)
                    if verbose:
                        print 'min distance with incorrect = ', minIncorrect
                # we check that there is a bump before the response
                if (isCorrectExists is True and isIncorrectExists is True and
                       minCorrect < maxThresh and minCorrect > minThresh and
                       minIncorrect < maxThresh and minIncorrect > minThresh):
                    raise ValueError('It seems that there are two bumps very close...')
                if (isCorrectExists is True and minCorrect < maxThresh and minCorrect > minThresh):
                    if verbose:
                        print 'this is a hit'
                    score = 1
                    hit += 1
                    answer = 'hit'
                    hitTime.append(i)
                    allHitTime.append(minCorrect)
                elif (isIncorrectExists is True and minIncorrect < maxThresh and minIncorrect > minThresh):
                    if verbose:
                        print 'this is a FA (false hit)'
                    score = 0
                    FA += 1
                    answer = 'FA'
                    falseHit += 1
                    falseHitTime.append(i)
                    allFalseHitTime.append(minIncorrect)
                else:
                    if verbose:
                        print 'this is a FA'
                    score = 0
                    FA += 1
                    answer = 'FA'
                    FATime.append(i)

        miss = gapNum - hit
        allFA = FA + falseHit

        hitRatio = hit/gapNum
        FARatio = allFA/gapNum

        # avoid infinite values in dprime calculation
        hitRatio1 = hitRatio
        FARatio1 = FARatio
        if hitRatio >= 1:
            hitRatio1 = 0.95
        if hitRatio <= 0:
            hitRatio1 = 0.05
        if FARatio <= 0:
            FARatio1 = 0.05
        if FARatio >= 1:
            FARatio1 = 0.95

        dprime = norm.ppf(hitRatio1) - norm.ppf(FARatio1)

        if verbose:
            print '\nhit = ', hit
            print 'FA = %s (including %s false hit)' % (FA, falseHit)
            print 'miss =', miss
            print 'gap =', gapNum


        if dataTrial.cloudCompNum.values[0] == 0:
            TC = False
        else:
            TC = True

        analyses.loc[trial] = [trial, dataTrial.freqDiff.values[0],
            hitRatio, hitRatio1, FARatio, FARatio1, falseHit, allFA, dprime,
            TC, dataTrial.correctStream.values[0], dataTrial.twoStreams.values[0],
            gapNum]

        if verbose:
            plt.figure()
            plotTrial(data, correctGap, incorrectGap, gapNum=gapNum, trial=trial,
                hitTime=hitTime, FATime=FATime, falseHitTime=falseHitTime, resp=resp)
            plt.show()
            plt.close()

        trial += 1
    return analyses

def plotTrial(data, correctBump, incorrectBump, gapNum, trial, hitTime, FATime, falseHitTime, resp):
    """
    Plot representation of the behavior trial. This shows the gaps of attended
    and unattended streams in green and red respectively and responses as
    vertical gray lines.
    still to implement...

    Parameters
    ----------

    Returns
    -------
    allTrials : instance of numpy.array
        List of trial numbers.
    """
    allXTicks = []
    for i in range(resp.shape[0]):
        plt.axvline(x=resp[i], color='gray')
    for i in range(gapNum):
        plt.axvline(x=correctBump[i], color='green')
        plt.axvline(x=incorrectBump[i], color='red')

        allXTicks.append(correctBump[i])
        allXTicks.append(incorrectBump[i])
    offset = 0.1
    for i in hitTime:
        plt.text(x=i-offset, y=0.5, s='H', color='green')
    for i in FATime:
        plt.text(x=i-offset, y=0.5, s='F', color='red')
    for i in falseHitTime:
        plt.text(x=i-offset, y=0.5, s='FH', color='red')
    plt.xlim(0, 15)
    plt.xticks(allXTicks, rotation=90)
    plt.title(trial)
    trial += 1

def checkLinkTrialsBehaviorEEG(trialBehavior, events, sessionNum, trigs, fs):
    """
    Check that answer recorded in behavior data correspond to triggers emitted
    by this answer. This allows to be sure that EEG data correspond to behavior.

    Parameters
    ----------
    fs : float
        EEG data sampling frequency in Hz.

    Returns
    -------

    """
    for trial in getTrialNumList(trialBehavior, sessionNum=sessionNum):
        print trial
        t0Sample = trigs.iloc[trial, 0]
        # get response in this trial
        ev = events[((events[:, 0]>t0Sample) & (events[:, 0]<t0Sample+(60*fs)) &
            (events[:, 2]==65312))]
        # why 100 ms difference with behavior data?
        print 'eeg     ', (ev[:, 0] - t0Sample)/fs + 0.1
        # print responses from behavior
        print 'behavior', trialBehavior.continuousResponses[trialBehavior.trialNum==trial].values[0]
        # plot 1 second before the beginning of the trial
        t0 = (t0Sample/fs)-1
        t1 = t0 + 32
        # data = pd.DataFrame(data[trial, :, :15])
        # plotDataSubset(data=data, stim=stim,
        #                lineTrigs=trigs,
        #                offset=1, t0=t0, t1=t1, fs=512.)

def getTrialNum(ref, allSubj, trialBehavior, **kwargs):
    """
    Get the trial numbers corresponding to specific conditions.

    Parameters
    ----------
    ref : int
        If 1: the condition is all trials (like for overall analyses: exp 1 and 2).
    allSubj : bool
        Choose to return the trial number for one or all subjects.
    trialBehavior : instance of Pandas.Dataframe
        All behavior data. Trial numbers will be find related to condition present
        in this dataset.
    **kwargs : other arguments
        All conditions can be passed as argument like `correctStream=[False]`.

    Returns
    -------
    allTrials : instance of numpy.array
        List of trial numbers.
    """
    if ref == 1:
        allTrials = np.arange(80)
    elif ref == 2:
        allTrials = np.arange(40)
    else:
        raise ValueError

    if (kwargs):
        acc = pd.DataFrame()
        for i in kwargs:
            acc[i] = trialBehavior[i].isin(kwargs[i])
        acc['res'] = acc.mean(axis=1)
        print kwargs
        results = trialBehavior.trialNum[acc['res']==1].values


        results = results[results>=0]
        if allSubj:
            results = np.concatenate([results, results+80,
                results+(80*2), results+(80*3)])
        return results
    else:
        if allSubj:
            allTrials = np.concatenate([allTrials, allTrials+80,
                allTrials+(80*2), allTrials+(80*3)])
        return allTrials

