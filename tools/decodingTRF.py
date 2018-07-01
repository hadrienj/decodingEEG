import numpy as np

def calculateCorr(env1, env2, fs, end=None):
    """
    Get correlations between env1 and env2 for each trials.

    Parameters
    ----------
    env1 : array-type
        First list of envelope of shape (trial, time).
    env2 : array-type
        Second list of envelope of shape (trial, time).
    fs : float
        Sampling frequency in Hz.
    end : float
        End limit in seconds to take for each trial.

    Returns:

    corrs : array-type
        List of correlations of shape (trial, 1).
    """
    if (env1.shape[0] != env2.shape[0] or env1.shape[1] != env2.shape[1]):
        raise ValueError("Shapes of the envelopes have to be identical\
 but they are: %s and %s" % (env1.shape, env2.shape))

    if end is None:
        end = env1.shape[1]
    else:
        end = int(np.round(fs*end))


    trials = env1.shape[0]
    corrs = np.zeros(trials)
    for trial in range(trials):
        corrs[trial] = np.corrcoef(env1[trial, :end],
                                   env2[trial, :end])[0, 1]

    return corrs

def getTRFAccuracyByDur(envAttended, envUnattended, envMismatch, envReconstructed, trials, trialsDualStream):
    """
    Get the classification accuracy according to duration of trials and trials used.

    Parameters
    ----------
    envAttended : instance of numpy.array
        Attended envelopes. Shape (trial, time).
    envUnattended : instance of numpy.array
        Unattended envelopes. Shape (trial, time).
    envMismatch : instance of numpy.array
        Mismatch envelopes (corresponding to another trial). Shape (trial, time).
    envReconstructed : instance of numpy.array
        Reconstructed envelopes. Shape (trial, time).
    trials : array-type
        Trials to consider.
    trialsDualStream : array-like
        Trials to consider in the exp 2 referential (attended vs unattended with
        only 40 trials)

    Returns
    -------
    classifMismatchTime : array-type
        List of classification accuracies (one value per second) for attended versus
        mismatch stream.
    classifAtt_unattTime : array-type
        List of classification accuracies (one value per second) for attended versus
        unattended stream (only trials included in the dual stream part).
    """
    # trialsUnattended = getUnattendedTrialsNumber(trials)
    # envUnattendedTrials = envUnattended[trialsUnattended]
    classifMismatchTime = []
    classifAtt_unattTime = []
    testAll = []
    # print 'trialsUnattended', trialsUnattended
    for i in range(0, 61):
        # Calculate all correlations without taking trials into account
        corrsAttended = calculateCorr(envAttended, envReconstructed,
            fs=64, end=i)

        corrsMismatch = calculateCorr(envMismatch, envReconstructed,
            fs=64, end=i)

        corrsUnattendedDualStream = calculateCorr(envUnattended,
            envReconstructed[trialsDualStream], fs=64, end=i)
        # print 'trialsDualStream', trialsDualStream
        # print 'corrsUnattendedDualStream', np.mean(corrsUnattendedDualStream)
        # Calculate the classification accuracy by selecting the trials to be used
        # Since the first trial dual streams is the number 40 we had to add 40 to the
        # trial number from the unattended part to the attended part
        classifMismatch = np.mean(corrsAttended[trials]>corrsMismatch[trials])
        classifMismatchTime.append(classifMismatch)

        classifAtt_unatt = np.mean(corrsAttended[trialsDualStream]>corrsUnattendedDualStream)
        classifAtt_unattTime.append(classifAtt_unatt)

        test = np.mean(corrsUnattendedDualStream>corrsMismatch[trialsDualStream])
        testAll.append(test)

    return classifMismatchTime, classifAtt_unattTime, testAll

def getUnattendedTrialsNumber(trials):
    """
    Get the trials for the condition dual streams. Since this condition was only from
    trial 40 to 80 these trials not all trials have to be considered.

    Parameters
    ----------
    trials : array-type
        Trials to consider.
    Returns:

    newEnv : array-type
        Envelope of the selected trials of shape (trials, time).
    """
    trialsUnattendedAll = np.arange(40, 80)
    trialsUnattendedIdx = np.isin(trials, trialsUnattendedAll)
    trialsUnattended = trials[trialsUnattendedIdx] - 40

    return trialsUnattended

