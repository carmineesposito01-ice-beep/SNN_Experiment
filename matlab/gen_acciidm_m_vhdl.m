function gen_acciidm_m_vhdl()
%GEN_ACCIIDM_M_VHDL  Rigenera il VHDL del blocco COMPLETO Donatello_ACC_IIDM_M (SNN+IIDM R17) in
%  matlab/hdl_acciidm_m/ (dir stabile, non temp), per la ri-sintesi OOC di conferma Fmax.
%  4 ingressi fisici (s,v,dv,v_l, fixed >=20 bit frazionari) -> accel. -top DUT per synth_acc_iidm.tcl.
  here=fileparts(mfilename('fullpath')); lib='snn_champions_lib';
  outdir=fullfile(here,'hdl_acciidm_m');
  if exist(outdir,'dir'), rmdir(outdir,'s'); end
  bdclose('all'); load_system(lib);
  blk=[lib '/Donatello_ACC_IIDM_M'];
  mdl='gen_acciidm_m'; new_system(mdl); load_system(mdl);
  sub=[mdl '/DUT']; add_block(blk, sub);
  vals={'10','6','2','4'};
  for j=1:4
    add_block('simulink/Sources/Constant',[mdl '/i' num2str(j)],'Value',vals{j}, ...
              'OutDataTypeStr','fixdt(1,32,20)','SampleTime','1');
    add_line(mdl,['i' num2str(j) '/1'],['DUT/' num2str(j)]);
  end
  add_block('built-in/Outport',[mdl '/accel'],'Port','1'); add_line(mdl,'DUT/1','accel/1');
  set_param(mdl,'Solver','FixedStepDiscrete','FixedStep','1','StopTime','10');
  set_param(mdl,'SimulationCommand','update');
  makehdl(sub,'TargetLanguage','VHDL','TargetDirectory',outdir,'GenerateHDLTestBench','off');
  v=dir(fullfile(outdir,'**','*.vhd'));
  fprintf('VHDL ACC_IIDM_M generato: %d file in %s\n', numel(v), outdir);
  close_system(mdl,0); close_system(lib,0);
end
