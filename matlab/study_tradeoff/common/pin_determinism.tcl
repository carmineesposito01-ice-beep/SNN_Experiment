# Prelude di DETERMINISMO per lo sweep min-slack (va sourced PRIMA di synth_point/impl_point).
#   vivado -mode batch -source pin_determinism.tcl -source synth_point.tcl -tclargs ...
#
# Perche': Vivado place/route e' deterministico a parita' di (versione, seed, numero di thread). Il seed
# di default e' 0 (fisso). Il numero di thread NO: dipende dalla macchina -> fissarlo rende il run
# riproducibile fra macchine, non solo run-to-run sulla stessa. Un valore FISSO qualsiasi e'
# deterministico sulla stessa macchina; 4 e' un compromesso velocita'/portabilita' (piu' alto = piu'
# veloce ma piu' sensibile fra macchine diverse). Lo si registra nell'output per audit.
set_param general.maxThreads 4
puts "PIN: maxThreads=[get_param general.maxThreads] (seed di default = 0, fisso)"
