fs = 64;
map = -1;
tmin = -50;
tmax = 300;
lambda = [0.00000001];

eeg = hdf5read('data_p1.h5', 'eeg_TRF');

att = hdf5read('data_p1.h5', 'envAttended');

% 80 trials
for i = 1:80
    eeg_set{1, i} = eeg(:, :, i)';
    att_set{1, i} = att(:, i)*2;
end


[r_att, p_att, ~, pred_att, model_att] = mTRFcrossval(att_set, eeg_set, fs, map, tmin, tmax, lambda);


% convert to h5
hdf5write('reconstructed_p1.h5', 'reconstructed', pred_att);
