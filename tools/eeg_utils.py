import numpy as np
import pandas as pd
from scipy import signal
from eeg import loadEEG, getEvents, chebyBandpassFilter, refToMastoids,\
    create3DMatrix, getTrialNumList, refToAverageNP
from behavior import getBehaviorData
import h5py

def processEEG(fnEEG, dbName, sessionNums, trialsToRemove, trialBehavior, fs, ref):
    """
    Load and process EEG from .bdf file. The data is filtered according to
    `freqFilter`, re-referenced according to the mastoids and downsampled
    to 64 Hz if `downsampling` is set to True.

    Parameters
    ----------
    fn : str
        Name of the bdf containing the EEG data.
    dbName : str
        Name of the database on the couch instance.
    sessionNums : array-type
        List of sessions to keep.
    trialsToRemove : array-type
        List of trials to remove from the analyses.
    ref : str
        Choose between referencing to mastoids ('mastoids') or to the average
        of all electrodes ('average').
    fs : float
        Sampling frequency in Hz.

    Returns
    -------
    dataFilt3D64 : instance of numpy.array
        A matrix of shape (trial, time, electrode) containing the processed data.
    """
    if ref != 'average' and ref != 'mastoids':
        raise ValueError('Bad `ref` argument!')

    # Loading
    raw = loadEEG(fnEEG)
    print raw.ch_names[:64]
    data = raw[:, :][0].T

    # Get triggers
    trigs = getEvents(raw=raw, eventCode=65282, shortest_event=1)
    # Some triggers have been sent but the trial not done due to experimental errors
    # Let's remove these trials in the EEG data
    newTrigs = trigs.drop(trigs.index[trialsToRemove]).reset_index(drop=True)

    # Filtering
    zpk, dataFiltTRF = chebyBandpassFilter(data, [0.5, 1, 14.5, 15], gstop=80, gpass=1,
        fs=fs)
    zpk, dataFiltSSR = chebyBandpassFilter(data, [0.5, 1, 100, 101], gstop=80, gpass=1,
        fs=fs)

    del data

    if ref=='mastoids':
        dataFiltTRF = pd.DataFrame(dataFiltTRF, columns=raw.ch_names)
        dataFiltSSR = pd.DataFrame(dataFiltSSR, columns=raw.ch_names)
        # Re-referencing
        dataFiltRefTRF = refToMastoids(dataFiltTRF,
                                    dataFiltTRF['M1'],
                                    dataFiltTRF['M2']).iloc[:, :64]
        del dataFiltTRF
        # Re-referencing
        dataFiltRefSSR = refToMastoids(dataFiltSSR,
                                    dataFiltSSR['M1'],
                                    dataFiltSSR['M2']).iloc[:, :64]
        del dataFiltSSR
    elif ref=='average':
        # Re-referencing
        dataFiltRefTRF = refToAverageNP(dataFiltTRF[:, :64])
        del dataFiltTRF
        # Re-referencing
        dataFiltRefSSR = refToAverageNP(dataFiltSSR[:, :64])
        del dataFiltSSR

        dataFiltRefTRF = pd.DataFrame(dataFiltRefTRF, columns=raw.ch_names[:64])
        dataFiltRefSSR = pd.DataFrame(dataFiltRefSSR, columns=raw.ch_names[:64])

    trialDur = 60
    # Changing shape to 3D matrix
    # Choose the length according to the number of sample in the sound files
    dataFilt3DTRF = create3DMatrix(data=dataFiltRefTRF, trialTable=trialBehavior,
                           events=newTrigs, trialList=getTrialNumList(trialBehavior),
                           trialDur=trialDur, fs=fs, normalize=False, baselineDur=0)
    del dataFiltRefTRF
    dataFilt3DSSR = create3DMatrix(data=dataFiltRefSSR, trialTable=trialBehavior,
                           events=newTrigs, trialList=getTrialNumList(trialBehavior),
                           trialDur=trialDur, fs=fs, normalize=False, baselineDur=0)

    del dataFiltRefSSR

    # Remove the first two seconds to avoid bias since in some trials one
    # stream starts 2 seconds before the other
    start = int(np.round(2*fs))
    # Remove last two seconds that should be less reliable
    end = start + int(np.round((trialDur - 2)*fs))

    dataFilt3DTRF = dataFilt3DTRF[:, start:end, :]
    dataFilt3DSSR = dataFilt3DSSR[:, start:end, :]

    # Downsampling
    dataFilt3DTRF64 = signal.decimate(dataFilt3DTRF, q=8, axis=1, zero_phase=True)

    return dataFilt3DTRF64, dataFilt3DSSR

def loadDataH5(path, pathReconstructed):
    """
    Load data from .h5 file. This expects to load one file containing the EEG
    and the envelopes of the stimuli and another file the reconstructed
    envelope created from Matlab.

    Parameters
    ----------
    path : str
        Path to the `.h5` file containing EEG and stimuli envelopes.
    pathReconstructed : str
        Path to the `.h5` file containing the reconstructed envelopes.

    Returns
    -------
    eeg_TRF : instance of numpy.array
        A matrix of shape (trial, time, electrode) containing the data processed
        for the TRF.
    eeg_TRF : instance of numpy.array
        to do.
    envMismatch : instance of numpy.array
        to do.
    envUnattended : instance of numpy.array
        to do.
    envReconstructed : instance of numpy.array
        to do.
    eeg_aSSR : instance of numpy.array
        to do.
    """
    f1 = h5py.File(path, 'r')
    eeg_TRF = np.array(list(f1['eeg_TRF']))
    eeg_aSSR = np.array(list(f1['eeg_aSSR']))
    envAttended = np.array(list(f1['envAttended']))
    envUnattended = np.array(list(f1['envUnattended']))
    f1.close()

    f2 = h5py.File(pathReconstructed, 'r')
    envReconstructed = np.array(list(f2['reconstructed']))
    f2.close()

    # Roll trials to create mismatch envelope:
    envMismatch = np.roll(envAttended, 1, axis=0)

    return eeg_TRF, envAttended, envMismatch, envUnattended, envReconstructed, eeg_aSSR

