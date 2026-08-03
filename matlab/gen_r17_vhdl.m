function gen_r17_vhdl()
%GEN_R17_VHDL  Rigenera il VHDL del blocco ACC-IIDM (R17) in matlab/hdl_iidm_r17/ (dir stabile, non temp),
%  per la sintesi di conferma Fmax. makehdl sul blocco istanziato con ingressi fixed >=20 bit frazionari.
  here=fileparts(mfilename('fullpath')); lib='snn_champions_lib';
  outdir=fullfile(here,'hdl_iidm_r17');
  if exist(outdir,'dir'), rmdir(outdir,'s'); end
  bdclose('all'); load_system(lib);
  blk=[lib '/ACC-IIDM'];
  mdl='gen_r17'; new_system(mdl); load_system(mdl);
  sub=[mdl '/DUT']; add_block(blk, sub);
  vals={'10','6','2','4','25','1.5','2','1.5','2'};
  for j=1:9
    add_block('simulink/Sources/Constant',[mdl '/i' num2str(j)],'Value',vals{j}, ...
              'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_line(mdl,['i' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('built-in/Outport',[mdl '/accel'],'Port','1'); add_line(mdl,'DUT/1','accel/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  set_param(mdl,'SimulationCommand','update');
  makehdl(sub,'TargetLanguage','VHDL','TargetDirectory',outdir,'GenerateHDLTestBench','off');
  v=dir(fullfile(outdir,'**','*.vhd'));
  fprintf('VHDL R17 generato: %d file in %s\n', numel(v), outdir);
  close_system(mdl,0); close_system(lib,0);
end
