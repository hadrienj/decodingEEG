import numpy as np
import pandas as pd
from eeg import computePickEnergy
from behavior import analyses

from sklearn import svm
from sklearn.model_selection import train_test_split

def calculateBaseline(data, fs):
    """
    Calculate the baseline in order to take into account the fact that the eeg
    response can be different for the two AM rates. This functions computes
    the ratio between the AM rates in the one stream condition.

    Parameters
    ----------
    eegData : instance of numpy.array
        EEG data of shape (trial, time, electrode).

    Returns
    -------
    ratio : float
        Ratio between the 36 Hz stream and the 44 Hz stream.
    """
    # Take only trials from 1 stream condition
    data36 = data[:10, :, :]
    data44 = data[20:30, :, :]
    # Average trials time domain
    data36MeanTrial = data36.mean(axis=0)
    data44MeanTrial = data44.mean(axis=0)

    # Compute picks for both streams
    pick36 = computePickEnergy(data36MeanTrial, pickFreq=36, showPlot=False, fs=fs)
    pick44 = computePickEnergy(data44MeanTrial, pickFreq=44, showPlot=False, fs=fs)
    # Average electrodes
    pick36Mean = np.mean(pick36)
    pick44Mean = np.mean(pick44)
    # Calculate baseline
    baseline = pick36Mean/pick44Mean
    return baseline

def comparePicks(data, fs):
    """
    Calculate the baseline in order to take into account the fact that the eeg
    response can be different for the two AM rates. This functions computes
    the ratio between the AM rates in the one stream condition.

    Parameters
    ----------
    eegData : instance of numpy.array
        EEG data of shape (time, electrode).

    Returns
    -------
    ratio : float
        Ratio between the 36 Hz stream and the 44 Hz stream.
    """
    pick36 = computePickEnergy(data, pickFreq=36, showPlot=False, fs=fs)
    pick44 = computePickEnergy(data, pickFreq=44, showPlot=False, fs=fs)
    ratio = pick36/pick44
    return ratio

def getSSRAccuracyByDur(data, trials, fs):
    """
    Get the classification accuracy according to duration of trials and trials used.

    Parameters
    ----------
    data : array-type
        Data to use to check accuracy.
    trials : array-type
        Trials to consider.
    fs : float
        Sampling frequency in Hz.

    Returns
    -------
    allComparisons : array-type
        Array containing all comparison (for each duration).
    """
    # Average data across trials
    dataSub = data[trials, :, :]

    allComparisons = np.zeros((59, 64))
    for dur in range(1, 60):
        durSamples = int(np.round(dur*fs))
        dataMeanTrial = dataSub[:, :durSamples, :].mean(axis=0)

        baseline = calculateBaseline(data[:, :durSamples, :], fs)

        electrodeComparison = comparePicks(dataMeanTrial, fs)
        electrodeBool = electrodeComparison>baseline

        allComparisons[dur-1, :] = electrodeBool
    return allComparisons

def crossVal(data, data1, fs):
    """
    This function has changed. To update and rename...

    Parameters
    ----------
    data : array-type
        Shape (trial, time, electrode). Compute pick at 36 Hz for each trial.
    data1 : array-type
        Shape (trial, time, electrode). Compute pick at 44 Hz for each trial.
    fs : float
        Sampling frequency in Hz.

    Returns
    -------
    aAll : array-type
        List of pick values for 36 Hz from `data`. Length of trial number.
    bAll : array-type
        List of pick values for 44 Hz from `data1`. Length of trial number.
    """
    testRatios = []
    aAll = []
    bAll = []
    accuracy = []
    # data36 = data[40:60, :, :]
    # data44 = data[60:80, :, :]
    # ratio44All = comparePicks(data44.mean(axis=0), fs)
    # ratio36All = comparePicks(data36.mean(axis=0), fs)
    # Training
    for trial in range(data.shape[0]):
        # print trial
        # if trial < 20:
        #     print 'Categorizing 36 Hz trial...'
        #     trainingData36 = np.delete(data36, trial, axis=0)
        #     ratio36 = comparePicks(trainingData36.mean(axis=0), fs)
        #     ratio44 = ratio44All
        # else:
        #     print 'Categorizing 44 Hz trial...'
        #     trainingData44 = np.delete(data44, trial-20, axis=0)
        #     ratio44 = comparePicks(trainingData44.mean(axis=0), fs)
        #     ratio36 = ratio36All
        # print '36, 44: ', ratio36.mean(), ratio44.mean()
        # Testing
        testData = data[trial, :, :]
        testData1 = data1[trial, :, :]
        # testRatio = comparePicks(testData, fs)
        # testRatios.append(testRatio.mean())

        a = computePickEnergy(testData, pickFreq=36, showPlot=False, fs=fs)
        b = computePickEnergy(testData1, pickFreq=44, showPlot=False, fs=fs)
        aAll.append(a.mean())
        bAll.append(b.mean())
        del a, b

        # print 'test ratio: ', testRatio.mean()
        # if np.abs(testRatio.mean() - ratio36.mean()) < np.abs(testRatio.mean() - ratio44.mean()):
        #     print 'Categorized as 36 Hz trial'
        #     if trial<20:
        #         accuracy.append(1)
        #     else:
        #         accuracy.append(0)
        # else:
        #     print 'Categorized as 44 Hz trial'
        #     if trial>20:
        #         accuracy.append(1)
        #     else:
        #         accuracy.append(0)
    return aAll, bAll

def hyperOptC(data, c_vals, durs, electrodes, dprimeThresh, subjNum, condition, fs, trialBehaviorAll):
    """
    Perform the hyper optimization of the c parameter of the SVM algorithm.
    Also compute the accuracy for a set of durations.

    Parameters
    ----------
    data : array-type
        Data to use. Shape (trial, time, electrode).
    c_vals : array-type
        List of c values to try.
    durs : array-type
        List of durations to use.
    electrodes : array-type
        List of electrodes to consider.
    dprimeThresh : float
        Threshold of dprime to include the trial as a good trial.
    subjNum : array-type
        List of subject to consider.
    condition : str
        'oneStream' or 'twoStreams': choose the condition.
    fs : float
        Sampling frequency in Hz.
    trialBehaviorAll : instance of pandas.Dataframe
        Behavior data from all participants.


    Returns
    -------
    bestC : instance of pandas.Dataframe
        Dataframe containing the accuracy for each c parameter and duration.
    """
    # Create dataframe to fill with the accuracy according to duration and c parameter
    bestC = pd.DataFrame(columns=['participant', 'dur', 'c', 'acc'])
    for dur in durs:
        durSamples = int(np.round(fs*dur))
        # Get pick values (36 and 44 Hz) for specific duration and electrodes
        pick36, pick44 = crossVal(data[:, :durSamples, :electrodes],
                                  data[:, :durSamples, :electrodes],
                                  fs=fs)
        # Reshape to have one column per participant and all trials (80) in each col
        allPicks36 = np.zeros((80, subjNum))
        allPicks44 = np.zeros((80, subjNum))
        for subj in range(subjNum):
            allPicks36[:80, subj] = pick36[80*subj:(80*subj)+80]
            allPicks44[:80, subj] = pick44[80*subj:(80*subj)+80]

        for i in range(subjNum):
            # remove bad trials (with dprime lower than dprime threshold) for this participant
            performances = analyses(trialBehaviorAll[i], verbose=False)
            badTrials = performances.trial[performances.dprime<dprimeThresh].values
            if condition=='oneStream':
                # Trials to take into account: only the first 40 for one stream condition
                trials = np.arange(40)
            elif condition=='twoStreams':
                # Trials to take into account: only the last 40 for two streams condition
                trials = np.arange(40, 80)
            else:
                raise ValueError('Wrong argument `condition`!')
            # Good trials are the wanted trials without the bad trials
            goodTrials = trials[~np.isin(trials, badTrials)]

            for c_val in c_vals:
                # Get only the good trials in our dataset
                X = np.array([allPicks36[goodTrials, i], allPicks44[goodTrials, i]]).T
                # Create labels
                if condition=='oneStream':
                    # We take the trials 40 to 80 and there were 20 36 Hz
                    # trials and then 20 44 Hz trials
                    y = np.concatenate([np.repeat(36, 20), np.repeat(44, 20)])[goodTrials]
                elif condition=='twoStreams':
                    # We need to add 40 trials at the beginning because the two streams
                    # trials are from 40 to 80
                    y = np.concatenate([np.arange(40),
                                        np.repeat(36, 20),
                                        np.repeat(44, 20)])[goodTrials]
                else:
                    raise ValueError('Wrong argument `condition`!')

                # Split dataset in train and test sets
                X_train, X_test, y_train, y_test = train_test_split(X, y,
                                                                    test_size=0.3,
                                                                    random_state=0)
                # Train SVM on train data
                clf = svm.SVC(kernel='rbf', C=c_val).fit(X_train, y_train)
                # Calculate accuracy on test data
                acc = clf.score(X_test, y_test)
                # Store accuracy
                bestC = bestC.append({'participant': i, 'dur': dur, 'c': c_val, 'acc': acc},
                             ignore_index=True)
    return bestC

def getBestAcc(durs, bestC):
    """
    Return the c parameter corresponding to the better accuracy for the 4
    participants and for each duration.

    Parameters
    ----------
    durs : array-type
        .List of durations to consider.
    bestC : instance of pandas.Dataframe
        Dataframe returned from the function 'hyperOptC'.

    Returns
    -------
    p1AccAll : array-type
        List of accuracies for each duration with the better c parameter
        (at 60s) for the participant 1.
    p2AccAll : array-type
        List of accuracies for each duration with the better c parameter
        (at 60s) for the participant 2.
    p3AccAll : array-type
        List of accuracies for each duration with the better c parameter
        (at 60s) for the participant 3.
    p4AccAll : array-type
        List of accuracies for each duration with the better c parameter
        (at 60s) for the participant 4.
    """
    # find value of c corresponding to the larger accuracy
    pIdx = bestC[bestC['dur']==60].groupby(['participant', 'dur'])['acc'].idxmax().values
    pC = bestC.iloc[pIdx].c.values.astype(int)
    print pC

    p1AccAll = []
    p2AccAll = []
    p3AccAll = []
    p4AccAll = []

    for i in range(len(durs)):
        p1Acc = bestC.acc[((bestC.participant == 0) & (bestC.c == pC[0]) &
                          (bestC.dur == durs[i]))].values
        p2Acc = bestC.acc[((bestC.participant == 1) & (bestC.c == pC[1]) &
                          (bestC.dur == durs[i]))].values
        p3Acc = bestC.acc[((bestC.participant == 2) & (bestC.c == pC[2]) &
                          (bestC.dur == durs[i]))].values
        p4Acc = bestC.acc[((bestC.participant == 3) & (bestC.c == pC[3]) &
                          (bestC.dur == durs[i]))].values
        p1AccAll.append(p1Acc)
        p2AccAll.append(p2Acc)
        p3AccAll.append(p3Acc)
        p4AccAll.append(p4Acc)

    return p1AccAll, p2AccAll, p3AccAll, p4AccAll

