function blkStruct = slblocks
% Libreria SNN
Browser(1).Library = 'snn_champions_lib';
Browser(1).Name    = 'SNN_Library';

% Libreria Modelli Car-Following
Browser(2).Library = 'cf_plant_lib';      % Nome del secondo file .slx (senza estensione)
Browser(2).Name    = 'Car-Following Models';    % Nome che apparirà nel Library Browser


blkStruct.Browser = Browser;
end

