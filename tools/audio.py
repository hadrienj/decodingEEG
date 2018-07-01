import numpy as np
from scipy.io import wavfile
from scipy import signal, fftpack
import urllib2, base64
from subprocess import Popen, PIPE
import soundfile as sf
import couchdb
from IPython.display import display, clear_output

def audioToNP(audioWebm, stream, verbose=False):
    """
    Get a list of matrices containing audio from a list of webm file.

    Parameters
    ----------
    audioList : array-like
        List containing audio matrices. Its length is the number of trial
    audioLen : int
        The number of samples in each trial.
    stream : str
        Multiple sounds are associated with each trial.
        Stream contains character to discriminate.
    verbose : bool
        If True, more information are displayed.

    Returns:

    audioList : array-like
        List of matrices audio as elements.
    audioLen : int
        Number of samples for each trial.
    """

    audioList = []
    trialLenAll = []

    for i in range(len(audioWebm)):
        for j in audioWebm[i].keys():
            if stream in j:
                audioName = j
        if verbose:
            # clear_output(wait=True)
            display('Fetching %s file...' % audioName)

        fs, audio = fromWebmToWav(inputFile=audioWebm[i][audioName],
            filename='test%d'%i, verbose=verbose)
        # remove second identical channel
        audio = audio[:, 0]
        # start with non 0 values
        audio = np.trim_zeros(audio, trim='f')
        trialLenAll.append(audio.shape[0])
        audioList.append(audio)

        trialLen = int(np.min(trialLenAll))

    return audioList, trialLen

def butterLpass(data, cutoff, fs, order=5):
    """
    Filter data with a low pass butterworth filter.

    Parameters
    ----------
    data : instance of numpy.array
        Matrix of shape (samples,) containing the signal to filter
    cutoff : float
        The cutoff frequency in Hz.
    fs : float
        The sampling frequency of the signal.
    order : int
        Order of the filter.

    Returns:

    y : instance of numpy.array
         Matrix of shape (samples,) containing the filtered signal.
    """
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    b, a = signal.butter(order, normal_cutoff, btype='low', analog=False)
    # using filtfilt instead of lfilt to avoid the offset of the window size
    y = signal.filtfilt(b, a, data)
    return(y)

def downsampleTo64(data):
    """
    Decimate data with a factor 750 to go from 48000 to 64 Hz.

    Parameters
    ----------
    data : instance of numpy.array
        Matrix to downsample.

    Returns:

    newdata : instance of numpy.array
        Downsampled matrix of shape (trial, time).
    """
    # The initial sampling rate is 48000. and we want to got to 64
    # It is done in multiple steps because the doc of scipy.signal.decimate
    # advice to use a factor bellow 13
    decimate_intermediate = [10, 5, 5, 3]
    newdata = data
    for i in decimate_intermediate:
        newdata = signal.decimate(newdata, q=i, axis=1, zero_phase=True)
    return newdata

def fromWebmToWav(inputFile, filename, verbose=False):
    """
    Convert webm file from database to wav by writing on disk. The files are
    not removed.

    Parameters
    ----------
    inputFile : webm file
        Webm audio file to convert into wav.
    filename : str
        Base name to use to store files on disk.
    verbose : bool
        If True, more information are displayed.

    Returns:

    allAudioFiles : array-like
        List of all audio files corresponding to the session, db etc.
    """
    audio_wav_file = inputFile
    filenameInput = '%s.webm' % filename
    filenameOutput = '%s.wav' % filename


    wavf = open(filenameInput, 'wrb')
    wavf.write(audio_wav_file)
    wavf.close()

    command = 'ffmpeg -i %s -y %s 2>&1' % (filenameInput, filenameOutput)

    conversion = Popen(command, shell = True, stdout = PIPE)
    # wait for the process to terminate
    out, err = conversion.communicate()
    errcode = conversion.returncode

    if verbose:
        # clear_output(wait=True)
        display(filenameOutput)

    fs, audio = wavfile.read(filenameOutput)
    return fs, audio

def getAudio(dbAddress, dbName, password, sessionNum, verbose=False):
    """
    Get names of audio files from couchdb. This allows for instance to use the
    names in the query to get the actual audio files.

    Parameters
    ----------
    dbAddress : str
        Path to the couch database.
    dbName : str
        Name of the database on the couch instance.
    password : str
        Password of the couch database
    sessionNum : int
        Filter trials from a specific session number.

    Returns:

    allAudioFiles : array-like
        List of all audio files corresponding to the session, db etc.
    """
    allAudioFileNames = getAudioFilenames(dbAddress, dbName, password, sessionNum)
    allAudioFiles = []
    for trial in allAudioFileNames:
        allAudioFiles.append({})
        audioFileNames = allAudioFileNames[trial]
        audioFilesTrial = []
        for audioFileName in audioFileNames:
            url = "%s%s/maskingEEG_%d_%d/%s" % (dbAddress, dbName, sessionNum, trial, audioFileName)
            if verbose:
                print url
            request = urllib2.Request(url)
            base64string = base64.encodestring('%s:%s' % (dbName, password)).replace('\n', '')
            request.add_header("Authorization", "Basic %s" % base64string)
            result = None
            while result is None:
                try:
                    result = urllib2.urlopen(request)
                except:
                    pass
            snd = result.read()
            allAudioFiles[trial][audioFileName] = snd
    return allAudioFiles

def getAudioFilenames(dbAddress, dbName, password, sessionNum):
    """
    Get names of audio files from couchdb. This allows for instance to use the
    names in the query to get the actual audio files.

    Parameters
    ----------
    dbAddress : str
        Path to the couch database.
    dbName : str
        Name of the database on the couch instance.
    password : str
        Password of the couch database
    sessionNum : int
        Filter trials from a specific session number.

    Returns:

    allAudioFileNames : dict
        Dictionary containing trial numbers as keys and array of audio file
        names as values.
    """

    couch = couchdb.Server(dbAddress)
    couch.resource.credentials = (dbName, password)
    db = couch[dbName]

    count = 0
    allAudioFiles = {}
    for doc in db.view('_all_docs'):
        if (doc['id'].startswith('maskingEEG_%d' % sessionNum)):
            allAudioFiles[db.get(doc['id'])['trialNum']] = db.get(doc['id'])['_attachments'].keys()
    return allAudioFiles

def getWebm(dbAddress, dbName, password, sessionNums):
    """
    Get webm audio files from couchdb.

    Parameters
    ----------
    dbAddress : str
        Path to the couch database.
    dbName : str
        Name of the database on the couch instance.
    password : str
        Password of the couch database
    sessionNums : array-like
        List of sessions to keep.

    Returns:

    allAudioFiles : array-like
        List of all audio files corresponding to the session, db etc.
    """
    allAudioFiles = []
    for sessionNum in sessionNums:
        audioFile = getAudio(dbAddress, dbName, password, sessionNum)
        allAudioFiles.append(audioFile)
    allAudioFiles = [item for sublist in allAudioFiles for item in sublist]
    return allAudioFiles

def getConcatAudio(audioList, trialLen, verbose=False):
    """
    Get all audio files under the form of one concatenated matrix containing the
    raw audio and another one containing the envelopes.

    Parameters
    ----------
    audioList : array-like
        List containing audio matrices. Its length is the number of trials.
    audioLen : int
        The number of samples in each trial.
    verbose : bool
        If True, more information are displayed.

    Returns:

    audioAll : instance of numpy.array
        Matrix of shape (samples,) containing all audio trials concatenated.
    audioAllEnv : instance of numpy.array
        Matrix of shape (samples,) containing all audio envelopes concatenated.
    """
    # The Hilbert transform can be very slow according to the number of samples used
    trialLenFastHilbert = fftpack.next_fast_len(trialLen)
    trialNum = len(audioList)

    audioAllEnv = np.zeros((trialNum*trialLen))
    audioAll = np.zeros((trialNum*trialLen))

    for i in range(len(audioList)):
        audio = audioList[i]
        audioAll[trialLen*i:trialLen*(i+1)] = audio[:trialLen]

        env = np.abs(signal.hilbert(audio, N=trialLenFastHilbert))

        if verbose:
            # clear_output(wait=True)
            display(i, 'envelope finished')

        audioAllEnv[trialLen*i:trialLen*(i+1)] = env[:trialLen]
        del env, audio

    return(audioAll, audioAllEnv)

def getEnv(dbAddress, dbName, password, verbose, sessionNums, fs, stream):
    """
    Get the requested envelope corresponding to the user, sessionNum, stream etc.

    Parameters
    ----------
    dbAddress : str
        Path to the couch database.
    dbName : str
        Name of the database on the couch instance.
    password : str
        Password of the couch database.
    verbose : bool
        If True, more information are displayed.
    sessionNums : array-like
        List of sessions to keep.
    fs : float
        Sampling frequency
    stream : str
        Stream to keep ('36' or '44').

    Returns:

    audioAllEnvFilt2DDS : instance of numpy.array
        Matrix of shape (trial, time) containing the envelope filtered.
    """
    audioWebm = getWebm(dbAddress, dbName, password, sessionNums)
    audioList, trialLen = audioToNP(audioWebm, stream, verbose)
    audioAll, audioAllEnv = getConcatAudio(audioList, trialLen, verbose)
    # Filtering
    audioAllEnvFilt = butterLpass(audioAllEnv, cutoff=15, fs=fs, order=5)
    totalTrialNum = len(audioList)
    # converting to 2D matrix
    audioAllEnvFilt2D = splitEnvInTrials(audioAllEnvFilt, totalTrialNum, trialLen)
    return audioAllEnvFilt2D

def getAttendedAndUnattendedEnv(dbAddress, dbName, password, verbose, fs=48000.):
    """
    Get all envelopes required for the analyses. The function will return
    3D matrices containing attended and unattended envelopes.

    Parameters
    ----------
    dbAddress : str
        Path to the couch database.
    dbName : str
        Name of the database on the couch instance.
    password : str
        Password of the couch database.
    verbose : bool
        If True, more information are displayed.
    sessionNums : array-like
        List of sessions to keep.
    stream : str
        Stream to keep ('36' or '44').
    fs : float
        Sampling frequency

    Returns:

    attended : instance of numpy.array
        Matrix of shape (trial, time) containing the envelope of all attended
        streams.
    unattended : instance of numpy.array
        Matrix of shape (trial, time) containing the envelope of all unattended
        streams.
    """
    print('This operation can takes few seconds/minutes... Please wait!')
    if verbose:
        print('noTC36...')
    noTC36 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[1],
        fs=fs, stream='36')
    if verbose:
        print('noTC44...')
    noTC44 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[3],
        fs=fs, stream='44')
    if verbose:
        print('TC36...')
    TC36 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[2],
        fs=fs, stream='36')
    if verbose:
        print('TC44...')
    TC44 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[4],
        fs=fs, stream='44')

    if verbose:
        print('stim36Att36...')
    stim36Att36 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[5, 6],
        fs=fs, stream='36')
    if verbose:
        print('stim44Att36...')
    stim44Att36 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[5, 6],
        fs=fs, stream='44')
    if verbose:
        print('stim36Att44...')
    stim36Att44 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[7, 8],
        fs=fs, stream='36')
    if verbose:
        print('stim44Att44...')
    stim44Att44 = getEnv(dbAddress, dbName, password, verbose, sessionNums=[7, 8],
        fs=fs, stream='44')

    # Remove the first two seconds to avoid bias since in some trials one
    # stream starts 2 seconds before the other
    start = int(np.round(2*fs))
    # Find the minimum duration among all envelopes in order to cut the others
    end = np.min([TC36.shape[1], TC44.shape[1], noTC36.shape[1], noTC44.shape[1],
        stim36Att36.shape[1], stim44Att36.shape[1], stim36Att44.shape[1],
        stim44Att44.shape[1]])

    # Create attended and unattended streams
    attended = np.concatenate([noTC36[:, start:end], TC36[:, start:end],
        noTC44[:, start:end], TC44[:, start:end], stim36Att36[:, start:end],
        stim44Att44[:, start:end]], axis=0)
    unattended = np.concatenate([stim44Att36[:, start:end],
        stim36Att44[:, start:end]], axis=0)

    # downsampling
    attendedDS = downsampleTo64(attended)
    unattendedDS = downsampleTo64(unattended)
    print('Done!')
    return attendedDS, unattendedDS

def splitEnvInTrials(data, totalTrialNum, trialLen, verbose=False):
    """
    Convert the concatenated array of sound to a 2D matrix of shape (trial, time).

    Parameters
    ----------
    data : instance of numpy.array
        Matrix of shape (samples,). Concatenated audio containing all trials in
        one 2D matrix.
    totalTrialNum : int
        The number of trials contained in the matrix data.
    trialLen : int
        The number of sample of one trial (we expect same length trials).

    Returns:

    newData : instance of numpy.array
        Matrix of shape (trial, time).
    """

    newData = np.zeros((totalTrialNum, trialLen))
    for trial in range(totalTrialNum):
        if verbose:
            print trial
        newData[trial, :trialLen] = data[trialLen*trial:trialLen*(trial+1)]
    return newData


