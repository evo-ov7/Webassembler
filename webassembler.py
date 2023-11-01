import sys,re,types,copy,os

flatten=True
debug=1
nodes={"module","func","table","memory","global","start","type"}

canonical_types={"i32","i64","f64","f32","v128","ref"}
vector_types={"i8x","s8x","i16x","s16x","i32x","s32x","i64x","s64x","f32x","f64x"}
simulated_types={"s32","s64"}|vector_types
singular_types={"i32","i64","f64","f32","ref","s32","s64"}
variable_types=canonical_types|simulated_types
singular_memorytypes={"s8","s8s64","i8","i8i64","s16","s16s64","i16","i16i64","i32i64","s32s64","low8","low16","low32"}
vector_memorytypes={"i8x8","s8x8","i16x4","s16x4","i32x2","s32x2","i8x1","i16x1","i32x1","i64x1","s8x1","s16x1","s32x1","s64x1","f32x1","f64x1","i32x0","i64x0","s32x0","s64x0","f32x0","f64x0"}#8[ ] 16[ ] 32[ ] 64[ ] []
atomic_operations={"notify","wait","atomic_load","atomic_store","aadd","asub","aor","axor","aand","xchg","cmpxchg"}
memory_types=singular_memorytypes|vector_memorytypes|variable_types

block_instructions={"loop","if","else","end"}
table_instructions={"table.get","table.set","table.size","table.grow","table.fill","table.copy"}
memory_instructions={"memory.size","memory.grow","memory.fill","memory.copy","memory.init","data.drop"}
immediate_instructions={"br","br_if","br_table","call","call_indirect","ref.func","ref.null","shuffle","memory.init","data.drop"}|table_instructions
vector_typecasts={"asi8x","ass8x","asi16x","ass16x","asi32x","ass32x","asi64x","ass64x","asf32x","asf64x","asv128"}
singular_typecasts={"asi","asf","ass"}
typecast_instructions=singular_typecasts|vector_typecasts
vector_typeconversions={"lowx2","highx2"}|vector_types
typeconversion_instructions=typecast_instructions|variable_types|vector_typeconversions
pseudo_instructions={"sx8","sx16","sx32","load","store","set","get","tee","subexpression"}|typeconversion_instructions
vector_instructions={"shuffle","swizzle","not","andnot","bitselect","any_true","all_true","bitmask","narrow","add_sat","sub_sat","avgr","q15mulr_sat","extmul_low","extmul_high","extadd_pairwise","dot","pmin","pmax"}
control_instructions={"br","br_if","br_table","call","call_indirect","return"}
sign_instructions={"div","rem","shr","lt","gt","le","ge","narrow","add_sat","sub_sat","extmul_high","extmul_low","min","max","extadd_pairwise","avgr","q15mulr_sat","dot"}
nullary_instructions={"br","unreachable","nop","ref.null","ref.func","table.size","memory.size","atomic.fence"}
unary_instructions={"clz","ctz","popcnt","abs","neg","ceil","floor","trunc","nearest","sqrt","eqz","br_if","br_table","call_indirect","drop","sx8","sx16","sx32","ref.is_null","not","any_true","all_true","bitmask","extadd_pairwise","table.get","memory.grow","data.drop"}|typeconversion_instructions
binary_instructions={"add","sub","mul","and","or","xor","shl","rotl","rotr","min","max","copysign","eq","ne","shuffle","swizzle","andnot","narrow","add_sat","sub_sat","dot","extmul_low","extmul_high","avgr","q15mulr_sat","pmin","pmax","table.set","table.grow"}|sign_instructions
ternary_instructions={"select","bitselect","table.fill","table.copy","memory.fill","memory.copy","memory.init"}
dynamic_arity_instructions={"call","call_indirect","return"}
no_result={"br","unreachable","nop","drop","br_if","br_table","return","table.fill","table.copy","memory.fill","memory.copy","memory.init","data.drop","atomic.fence"}
i32_result={"eqz","ref.is_null","any_true","all_true","bitmask","table.size","table.grow","memory.size","memory.grow"}
ref_result={"ref.null","ref.func","table.get"}
different_resulttype=typeconversion_instructions|{"call","call_indirect","narrow","extmul_low","extmul_high","extadd_pairwise","eq","ne","lt","gt","le","ge"}
typeless_instructions=no_result|control_instructions|{"select","set","get","tee","subexpression","ref.is_null","atomic.fence"}|ref_result|table_instructions|memory_instructions
static_returntype={"const"}
static_vectortype={"not","and","andnot","or","xor","bitselect","any_true"}
instructions=nullary_instructions|unary_instructions|binary_instructions|ternary_instructions|dynamic_arity_instructions

#enhancements:
#support all module elements
#allow explicit instruction types (i64.add) - doesn't make sense without implicit typeconversions
#explicit block instruction
#pointer types
#simple substitution macros
#structs
#allow indices instead of identifiers
#break and continue (multi level)
#multiple declarations
#type inference
#any error checking

def warning(context,token,message,kind="Warning"):
  line = context.line
  linecount = context.position
  print(line)
  marker=""
  for i in range(token[0]+token[1]):
    if i<token[0]:
      marker+=" "
    else:
      marker+="^"
  print(marker)
  print(kind+" in line",str(linecount),":",message)

def error(context,token,message):
  warning(context,token,message,"Error")
  sys.exit(1)

def parse_type(string):
  type = types.SimpleNamespace()
  type.size = string[1:]
  if string[-1]=="x":
    type.size=string[1:-1]
  elif string=="ref":
    type.size=""
  type.canonical = string
  if string[-1]=="x":
    type.canonical="v128"
    type.shape=string+str(128//int(type.size))
  if string=="v128":
    type.shape="v128"
  if string[0]=="s":
    type.sign="s"
    if type.canonical!="v128":
      type.canonical="i"+type.canonical[1:]
    else:
      type.shape="i"+type.shape[1:]
  else:
    type.sign="u"
  return type

def tokenize(line):
  tokens = []
  tokenpositions =[]
  indentation=len(line)-len(line.lstrip(" "))
  line=line.strip(" ")
  if len(line)>1 and line[0]=="(" and line[-1] == ")":
    line=line[1:-1]
    line=line.strip(" ")
  comment=""
  token=""
  nested=0
  name=False
  for i,chara in enumerate(line):
    if comment:
      comment+=chara
    elif name:
      token+=chara
      if chara=='"':
        name=False
        tokens.append(token)
        token=""
        tokenpositions[-1][1]=i
    elif nested:
      token+=chara
      if chara in {"(","["}:
        nested+=1
      elif chara in {")","]"}:
        nested-=1
        if not nested and chara == ")":
          tokens.append(token)
          token=""
          tokenpositions[-1][1]=i
    elif chara in {" ",";","(","[",'"'}:
      if token:
        tokens.append(token)
        token=""
        tokenpositions[-1][1]=i
      if chara == ";":
        comment=chara
      if chara in {"(","["}:
        token=chara
        tokenpositions.append([i,i+1])
        nested+=1
      if chara =='"':
        token=chara
        tokenpositions.append([i,i+1])
        name=True
    else:
      if not token:
        tokenpositions.append([i,i+1])
      token+=chara
  if token:
    tokens.append(token)
    tokenpositions[-1][1]=len(line)
  if comment:
    comment=comment[1:]
  return tokens,tokenpositions,comment,indentation

def parse_const(string):
  type=types.SimpleNamespace()
  type.sign="u"
  type.size="32"
  output=""
  kind="i"
  if "." in string or "nan" in string or "inf" in string:
    kind="f"
  if "," in string:
    consts=string.split(",")
    type.canonical="v128"
    type.size=str(128//len(consts))
    type.shape=kind+type.size+"x"+str(len(consts))
    if kind == "i" and ("-" in string or "+" in string):
      type.sign="s"
    output="v128.const "+type.shape
    for const in consts:
      output+=" "+const
  else:
    if string[-1]=="_":
      output= kind+"64.const "+string[:-1]
      type.size="64"
      type.canonical=kind+"64"
    else:
      output= kind+"32.const "+string
      type.canonical=kind+"32"
    if (string[0]=="-" or string[0]=="+") and type.canonical[0]=="i":
      type.sign="s"
  return output,type

def parse_identifier(string):
  access=""
  if string[0] == "=":
    access="pass"
    string=string[1:]
  elif string[-1] == "=":
    access="write"
    string=string[:-1]
  else:
    access="read"
  return string,access

def parse_variable(string,function,module):
  string,access = parse_identifier(string)
  scope="local"
  if string[:7] == "global:":
    scope="global"
    string = string[7:]
  output=""
  type=None
  if scope=="local":
    type=function.locals[string]
  elif scope=="global":
    type = module.globals[string]
  if access == "read":
    output = scope+".get $"+string
  elif access == "write":
    output = scope+".set $"+string
  elif access == "pass":
    output = "local.tee $"+string
  return output,type,access

def stack_to_string(stack):
  output=""
  for type in stack:
    output+=" "+type.canonical
  return output

def parse_function_type(tokens):
  subtokens,_,_,_=tokenize(tokens.pop(0))
  output=""
  function_type=types.SimpleNamespace()
  function_type.params=[]
  function_type.results=[]
  if subtokens:
    output="(param"
    while subtokens:
      type=parse_type(subtokens.pop(0))
      function_type.params.append(type)
      output+=" "+type.canonical
    output+=")"
  subtokens,_,_,_=tokenize(line.pop(0))
  if subtokens:
    output+="(result"
    while subtokens:
      type=parse_type(subtokens.pop(0))
      function_type.results.append(type)
      output+=" "+type.canonical
    output+=")"
  return output,function_type

def finalize_instruction(instruction,output):
  if instruction.results==["same"]:
    if len(instruction.inputs)>1 and instruction.kind not in{"replace_lane","extract_lane","shr","shl"}:
      instruction.results[0]=instruction.inputs[1]
    else:
      instruction.results[0]=instruction.inputs[0]
  elif instruction.results==[None] and instruction.kind in {"eq","ne","lt","gt","le","ge"}:
    if instruction.inputs[0].canonical != "v128":
      instruction.results[0]=parse_type("i32")
    else:
      instruction.results[0]=parse_type("i"+instruction.inputs[0].size+"x")
  new_output=""
  if instruction.body=="":
    if instruction.kind in typecast_instructions:
      source_type=instruction.inputs[0]
      if instruction.kind  in {"asf","asi","ass"}:
        destination_type=parse_type(instruction.kind[2]+source_type.size)
        instruction.results=[destination_type]
        new_output=None
        if source_type.canonical[0]!=destination_type.canonical[0]:
          new_output=destination_type.canonical+".reinterpret_"+source_type.canonical
      elif instruction.kind in vector_typecasts:
        destination_type=parse_type(instruction.kind[2:])
        instruction.results=[destination_type]
        new_output=None
    elif instruction.kind in typeconversion_instructions:
      source_type=instruction.inputs[0]
      destination_type=instruction.results[0]
      if instruction.kind in singular_types and destination_type.canonical != source_type.canonical:
        new_output=destination_type.canonical
        if source_type.canonical=="i64" and destination_type.canonical=="i32":
          new_output+=".wrap_i64"
        elif source_type.canonical=="i32" and destination_type.canonical=="i64":
          new_output+=".extend_i32_"+source_type.sign
        elif destination_type.canonical[0]=="i" and source_type.canonical[0]=="f":
          new_output+=".trunc_sat_"+source_type.canonical+"_"+destination_type.sign
        elif destination_type.canonical[0]=="f" and source_type.canonical[0]=="i":
          new_output+=".convert_"+source_type.canonical+"_"+source_type.sign
        elif source_type.canonical=="f64" and destination_type.canonical=="f32":
          new_output+=".demote_f64"
        elif source_type.canonical=="f32" and destination_type.canonical=="f64":
          new_output+=".promote_f32"
      elif instruction.kind in vector_types and source_type.canonical in singular_types:
        new_output=destination_type.shape+".splat"
      elif instruction.kind in vector_types and destination_type.shape != source_type.shape:
        new_output=destination_type.shape
        if destination_type.shape[0]=="i":
          new_output+=".trunc_sat_"+source_type.shape+"_"+source_type.sign
          if source_type.size=="64":
            new_output+="_zero"
        elif source_type.shape[0]=="i":
          new_output+=".convert_"
          if destination_type.size=="64":
            new_output+="low_"
          new_output+=source_type.shape+"_"+source_type.sign
        elif destination_type.shape=="f32x4":
          new_output+=".demote_f64x2_zero"
        elif destination_type.shape=="f64x2":
          new_output+=".promote_low_f32x4"
      elif instruction.kind in vector_typeconversions:
        destination_type=parse_type(source_type.sign+str(int(source_type.size)*2)+"x")
        instruction.results=[destination_type]
        new_output=destination_type.shape+".extend_"+instruction.kind[:3]+"_"+source_type.shape+"_"+source_type.sign
      else:
        new_output=None
    elif instruction.kind in sign_instructions:
      type1 = instruction.inputs[0]
      type2 = instruction.inputs[1]
      if type1.canonical[0]=="f" or (type1.canonical=="v128" and type1.shape[0]=="f"):
        if type1.canonical=="v128":
          new_output=instruction.results[0].shape+"."+instruction.kind
        else:
          new_output=instruction.results[0].canonical+"."+instruction.kind
      else:
        if type1.sign !="u":
          instruction.results=[type1]
        else:
          instruction.results=[type2]
        if instruction.results[0].canonical=="v128":
          if instruction.kind in {"narrow","extmul_low","extmul_high","extadd_pairwise","dot"}:
            source_type=instruction.results[0]
            sign=source_type.sign
            if instruction.kind=="dot":
              source_type=parse_type("s"+source_type.shape[1:])
            if instruction.kind != "narrow":
              size=str(int(source_type.size)*2)
            else:
              size=str(int(source_type.size)//2)  
            instruction.results[0]=parse_type(sign+size+"x")
            new_output=instruction.results[0].shape+"."
            new_output+=instruction.kind+"_"+source_type.shape+"_"+source_type.sign
          elif instruction.kind == "avgr":
            new_output=instruction.results[0].shape+".avgr_u"
          elif instruction.kind == "q15mulr_sat":
            new_output=instruction.results[0].shape+".q15mulr_sat_s"
          else:
            new_output=instruction.results[0].shape+"."+instruction.kind+"_"+instruction.results[0].sign
        else:
          new_output=instruction.results[0].canonical+"."+instruction.kind+"_"+instruction.results[0].sign
    elif instruction.kind in{ "replace_lane","extract_lane"}:
      if instruction.kind=="replace_lane":
        vector_type=instruction.results[0]
        new_output=vector_type.shape+".replace_lane "+instruction.lane
      elif instruction.kind=="extract_lane":
        vector_type=instruction.inputs[0]
        if int(vector_type.size)<32:
          lane_type=parse_type(vector_type.sign+"32")
          instruction.results=[lane_type]
          new_output=vector_type.shape+".extract_lane_"+vector_type.sign+" "+instruction.lane
        else:
          lane_type=parse_type(vector_type.sign+vector_type.size)
          instruction.results=[lane_type]
          new_output=vector_type.shape+".extract_lane "+instruction.lane
    elif instruction.kind in {"load","store"}:
      if instruction.kind == "load":
        type=instruction.results[0]
      elif instruction.kind == "store":
        type=instruction.inputs[1]
      new_output="v128."+instruction.kind+type.size+"_lane"+instruction.private_body
    elif instruction.kind in atomic_operations:
      if instruction.kind=="atomic_load":
        destination_type="i32"
        memory_size=""
        if instruction.memorytype:
          if re.match(".*64$",instruction.memorytype):
            destination_type=instruction.memorytype[:-3]
            if instruction.memorytype[:-3]:
              memory_size=instruction.memorytype[1:-3]
          else:
            memory_size=instruction.memorytype[1:]
        destination_type=parse_type(destination_type)
        instruction.results=[destination_type]
        new_output=destination_type.canonical+".atomic.load"+memory_size
        if memory_size:
          new_output+="_u"+instruction.private_body
      elif instruction.kind=="wait":
        new_output="memory.atomic.wait"+instruction.results[0].size+instruction.private_body
      else:
        operation=instruction.kind
        if re.match("atomic",operation):
          operation=operation[7:]
        new_output=instruction.inputs[1].canonical+".atomic."
        memorytype=""
        if instruction.memorytype:
          memorytype=instruction.memorytype[1:]
        if instruction.kind != "atomic_store":
          new_output+="rmw"+memorytype+"."+operation
        else:
          new_output+="store"+memorytype
        if instruction.memorytype:
          new_output+="_u"
        new_output+=instruction.private_body
        
  elif instruction.kind not in typeless_instructions and instruction.kind not in static_returntype:
    type=None
    if instruction.kind in {"store","eq","ne","all_true","bitmask"}:
      if len(instruction.inputs)>1:
        type=instruction.inputs[1]
      else:
        type=instruction.inputs[0]
    else:
      type=instruction.results[0]
    if instruction.kind not in {"load","extract_lane"}:
      if type.canonical=="v128" and instruction.kind not in static_vectortype:
        new_output=type.shape+"."
      else:
        new_output=type.canonical+"."
  elif instruction.kind=="subexpression":
    new_output=None
  if new_output!=None:
    output=output[:instruction.position]+"("+new_output+output[instruction.position:]+")"
  return output

def parse_instruction(instruction,tokens,function,module,context):
  token=tokens.pop(0)
  if token in instructions or re.match(r'x\[.+\]$',token) or re.match(r'x\[[0-9]+\]=$',token):
    instruction.kind=token
    if token in nullary_instructions:
      instruction.required_inputs=0
    elif token in unary_instructions:
      instruction.required_inputs=1
    elif token in binary_instructions:
      instruction.required_inputs=2
    elif token in ternary_instructions:
      instruction.required_inputs=3
    elif token in dynamic_arity_instructions:
      if token == "call":
        instruction.required_inputs=len(module.functions[tokens[0]].params)
      elif token == "return":
        instruction.required_inputs=len(function.results)
    if token in no_result:
      instruction.results=[]
    elif token in i32_result:
      instruction.results=[parse_type("i32")]
    elif token in ref_result:
      instruction.results=[parse_type("ref")]        
    elif token in different_resulttype:
      if token in variable_types:
        instruction.results=[parse_type(token)]
      elif token == "call":
        instruction.results=module.functions[tokens[0]].results
      else:
        instruction.results=[None]
    else:
      instruction.results=["same"]
    if token in immediate_instructions:
      instruction.body=token
      if token == "shuffle":
        indices=tokens.pop(0)
        indices=indices.split(",")
        for index in indices:
          instruction.body+=" "+index
      else:
        if token == "br_table":
          table=tokens.pop(0)
          table=table.split(",")
          for label in table:
            instruction.body+=" $"+label+":"
        instruction.body+=" $"+tokens.pop(0)
        if token in {"br","br_if"}:
          instruction.body+=":"
        elif token == "table.copy":
          instruction.body+=" $"+tokens.pop(0)
        elif token == "call_indirect":
          if tokens[0][0]=="(":
            body,function_type=parse_function_type(tokens)
          else:
            name=tokens.pop(0)
            body+=" $"+name
            function_type=module.function_types[name]
          instruction.required_inputs=len(function_type.params)
          instruction.results=function_type.results
          instruction.body+=" "+body
      
    elif token in different_resulttype or token in sign_instructions:
      instruction.body=""
    elif token in pseudo_instructions:
      if token in {"sx8","sx16","sx32"}:
        instruction.body="extend"+token[2:]+"_s"
    else:
      instruction.body=token
    if re.match(r'x\[.+\]$',token):
      instruction.required_inputs=1
      lane=token[2:-1]
      instruction.lane=lane
      instruction.results=[None]
      instruction.kind="extract_lane"
      instruction.body=""
    elif re.match(r'x\[[0-9]+\]=$',token):
      instruction.required_inputs=2
      token=token[2:-2]
      instruction.results=["same"]
      instruction.kind="replace_lane"
      instruction.lane=token
      instruction.body=""
  elif token[0]=="[" and (token[-1]=="]" or len(token)>1 and token[-2:]=="]="):
    operation="load"
    if token[-1]=="=":
      operation="store"
      token=token[:-1]
    instruction.kind=operation
    instruction.required_inputs=1
    token=token[1:-1]
    if operation == "store":
      subexpression=""
      while tokens:
        subexpression+=tokens.pop(0)+" "
      if subexpression:
        tokens.append("("+subexpression+")")
    subexpression,immediate = token.rsplit(" ",1)
    if subexpression:
      tokens.insert(0,"("+subexpression+")")
    immediate=immediate[1:]
    offset=""
    memorytype=""
    alignment=""
    if immediate:
      immediates=immediate.split(",")
      if re.match(r'[a-z[]',immediates[0]):
        memorytype=immediates.pop(0)
      else:
        offset=" offset="+immediates.pop(0)
        if immediates and re.match(r'[a-z[]',immediates[0]):
          memorytype=immediates.pop(0)
      if immediates:
        alignment=" align="+immediates.pop(0)
    lane=""
    if memorytype=="notify":
      instruction.kind="notify"
      instruction.required_inputs=2
      instruction.results=[parse_type("i32")]
      instruction.body="memory.atomic.notify"
    elif memorytype=="wait":
      instruction.kind="wait"
      instruction.required_inputs=3
      instruction.results=["same"]
    elif memorytype and memorytype not in memory_types and "[" not in memorytype:
      operation2=re.match(r'[a-z]+',memorytype).group()
      if operation2[-1]=="i":
        operation2=operation2[:-1]
      instruction.memorytype=memorytype[len(operation2):]
      if operation2[-3:] == "low":
        operation2=operation2[:-3]
      if operation2 == "atomic":
        operation2+="_"+operation
      operation=operation2
      if operation in{"atomic_load","atomic_store"}:
        if operation == "atomic_load":
          instruction.required_inputs=1
          instruction.results=[None]
        elif operation == "atomic_store":
          instruction.required_inputs=2
          instruction.results=[]
      else:
        instruction.results=["same"]
        if operation == "cmpxchg":
          instruction.required_inputs=3
        else:
          instruction.required_inputs=2
      instruction.kind=operation
    elif operation == "load":
      sourcetype=None
      destinationtype=None
      if memorytype in variable_types:
        destinationtype=parse_type(memorytype)
        instruction.body=destinationtype.canonical+".load"
      elif "x" in memorytype :
        destinationtype=parse_type(memorytype[:-1])
        if memorytype[-1]=="0":
          instruction.body="v128.load"+destinationtype.size+"_zero"
        elif memorytype[-1]=="1":
          instruction.body="v128.load"+destinationtype.size+"_splat"
        else:
          instruction.body="v128.load"+memorytype[1:-1]+"_"+destinationtype.sign
      elif "[" in memorytype:
        destinationtype="same"
        instruction.required_inputs=2
        memorytype=memorytype[:-1]
        size,id=memorytype.split("[")
        lane=" "+id
      else: 
        if len(memorytype)<=3:
          sourcetype=parse_type(memorytype)
          destinationtype=parse_type(memorytype[0]+"32")
        else:
          sourcetype=parse_type(memorytype[:-3])
          destinationtype=parse_type(memorytype[-3:])
        instruction.body=destinationtype.canonical+".load"+sourcetype.size+"_"+sourcetype.sign
      instruction.results=[destinationtype]
    elif operation == "store":
      if "[" not in memorytype:
        instruction.body="store"+memorytype.lstrip("low")
      else:
        memorytype=memorytype[:-1]
        size,id=memorytype.split("[")
        lane=" "+id
      instruction.required_inputs=2
      instruction.results=[]
    if instruction.body:
      instruction.body+=offset+alignment+lane
    else:
      instruction.private_body=offset+alignment+lane
  elif re.match(r'[-+]?([0-9]|inf$|inf,|nan,|nan$|nan:0x)',token):
    instruction.kind="const"
    instruction.required_inputs=0
    instruction.body,type = parse_const(token)
    instruction.results=[type]
  else:
    instruction.body,type,access=parse_variable(token,function,module)
    instruction.kind="tee"
    if access=="write":
      instruction.required_inputs=1
      instruction.kind="set"
    elif access=="read":
      instruction.results=[type]
      instruction.kind="get"

def parse_expression(tokens,function,module,context):
  stackframe=len(function.stack)
  instruction_stack=[]
  output=""
  while tokens:
    if output:
      output+=" "
    instruction=types.SimpleNamespace()
    instruction.required_inputs=0
    instruction.inputs=[]
    instruction.results=[]
    instruction.position=len(output)
    instruction.body=""
    instruction.kind=""
    if tokens[0][0]=="(":
      old_length=len(function.stack)
      suboutput=parse_expression(tokenize(tokens[0])[0],function,module,context)#todo tokenize metadata needs to go into context here for proper error reporting
      new_length=len(function.stack)-old_length
      if new_length<0:
        stackframe+=new_length
      elif new_length>0:
        instruction.results.extend(function.stack[-new_length:])
        function.stack=function.stack[:-new_length]
      instruction.body=suboutput
      instruction.kind="subexpression"
      tokens.pop(0)
    else:
      parse_instruction(instruction,tokens,function,module,context)
      if instruction.required_inputs==1:
        instruction.old_stackframe=stackframe
        instruction.stackframe=len(function.stack)
    output+=instruction.body
    instruction_stack.append(instruction)
    while instruction_stack and (instruction_stack[-1].required_inputs==0 or not tokens or len(function.stack)-stackframe>=instruction_stack[-1].required_inputs and instruction_stack[-1].kind not in {"set"} and not (instruction_stack[-1].required_inputs==1 and instruction_stack[-1].old_stackframe==stackframe and instruction_stack[-1].stackframe==len(function.stack))):
      if debug >1:
        print(output)
        print(instruction_stack)
      instruction=instruction_stack.pop()
      if instruction.required_inputs==0:
        output=finalize_instruction(instruction,output)
        function.stack.extend(instruction.results)
      else:
        if len(function.stack)<instruction.required_inputs:
          error(context,[0,len(context.line)],"not enough values on the stack")
        instruction.inputs.extend(function.stack[-instruction.required_inputs:])
        function.stack=function.stack[:-instruction.required_inputs]
        output=finalize_instruction(instruction,output)
        function.stack.extend(instruction.results)
    if debug>1:
      print(output)
      print(instruction_stack)
  return output

def parse_single_block_header(tokens,position,function,module,context):
  token=tokens.pop(0)
  block=types.SimpleNamespace()
  block.labelstack=[]
  block.position=position
  block.kind=token
  block.name=""
  block.params=""
  block.old_stack=[]
  block.nested=False
  if block.kind =="else":
    return block
  if function.stack:
    block.params="(param"+stack_to_string(function.stack)+")"
  if tokens:
    token=tokens[0]
    if block.kind == "loop":
      tokens.pop(0)
      block.name=token
    elif block.kind == "if":
      block.condition=parse_expression(tokens,function,module,context)
      function.stack.pop()#condition
      params=stack_to_string(function.stack)
      block.old_stack=copy.copy(function.stack)
      if params:
        block.params="(param"+params+")"
      else:
        block.params=""
  return block

def block_to_string(block,stack):
  if block.kind=="if":
    output="(if"
  else:
    output=block.kind
  if block.name:
    output+=" $"+block.name
  if block.params:
    output+=" "+block.params
  if stack:
    output+="(result"+stack_to_string(stack)+")"
  if block.kind=="if":
    if block.condition:
      if flatten:
        output=block.condition+" "+output
      else:
        output+=" "+block.condition
    output+=" (then"
  for label in reversed(block.labelstack):
    output+=" block $"+label.name
    if block.params:
      output+=" "+block.params
    if label.results:
      if not block.params:
        output+=" "
      output+=label.results
  return output

def parse_function_body(function,module):
  function.stack=[]
  function.labelstack=[]
  blockstack=[function]
  output_body=[]
  context=types.SimpleNamespace()
  declarations=set()
  for linecount,line in enumerate(function.body):
    #line=function.body[linecount]
    context.line=function.lines[linecount]
    context.position=function.position+linecount
    tokenposition = function.tokenpositions[linecount]
    comment = function.comments[linecount]
    indentation= function.indentations[linecount]
    output=indentation*" "
    if line:
      token=line[0]
      if debug:
        print(line)
      if token[-1]==":":
        label = types.SimpleNamespace()
        label.name = token
        label.results = ""
        if function.stack:
          label.results = "(result"+stack_to_string(function.stack)+")"
        blockstack[-1].labelstack.append(label)
        output+="end $"+token

      elif token in block_instructions:
        token=line[0]
        if token =="end":
          while line and line[0]=="end":
            line.pop(0)
            block=blockstack.pop()
            if line and line[0]!="end":
              if block.kind=="else":
                block.ifblock.name=line.pop(0)
              else:
                block.name=line.pop(0)
            if block.kind !="else":
              indent=" "
              if not block.nested:
                indent=function.indentations[block.position]*" "
              output_body[block.position]=indent+block_to_string(block,function.stack)+output_body[block.position]
            else:
              output_body[block.position]=function.indentations[block.position]*" "+")(else"+output_body[block.position]
              block=block.ifblock
              indent=" "
              if not block.nested:
                indent=function.indentations[block.position]*" "
              output_body[block.position]=indent+block_to_string(block,function.stack)+output_body[block.position]
            if debug:
              print(function.lines[block.position])
              print(output_body[block.position])
            if block.kind=="loop":
              output+="end"
              if block.name:
                output+=" $"+block.name
            else:
              output+="))"
              if block.name and (not line or line[0]!="end"):
                output+=";;"+block.name
            if line and line[0]=="end":
              output+=" "
        else:
          nested=False
          output=""
          if token == "else":
            block=parse_single_block_header(line,len(output_body),function,module,context)
            ifblock =blockstack.pop()
            block.ifblock=ifblock
            function.stack=ifblock.old_stack
            blockstack.append(block)
            if line:
              token = line[0]
              nested=True
          if token != "else":
            block=parse_single_block_header(line,len(output_body),function,module,context)
            block.nested=nested
            blockstack.append(block)
      else:
        if token in variable_types:
          line.pop(0)
          while line:
            name,access = parse_identifier(line[0])
            type=parse_type(token)
            function.locals[name]=type
            function.head+="(local $"+name+" "+type.canonical+")"
            if access == "read":
              line.pop(0)
            else:
              break
          if not line:
            declarations.add(linecount)
        if line:
          output+=parse_expression(line,function,module,context)
    if comment:
        output+=" ;;"+comment
    if debug:
      print(output)
      if function.stack:
        print("stack: ",stack_to_string(function.stack))
      print()
    output_body.append(output)
  output=""
  for linecount,line in enumerate(output_body):
    if linecount not in declarations:
      output+=line+"\n"
  output+=")\n"
  return output

def parse_export_import(line,name):
  output=""
  if line and line[0]=="export":
    line.pop(0)
    if line and  line[0][0]!='"':
      output+=" (export \""+name+"\")"
    while line and line[0][0]=='"':
      output+=" (export "+line.pop(0)+")"
  if line and line[0]=="import":
    line.pop(0)
    if line[0][0]!='"':
      output+=" (import \"global\" \""+name+"\")"
    elif line[1][0]!='"':
      output+=" (import \"global\" \""+line.pop(0)+"\")"
    else:
      output+=" (import "+line.pop(0)+" "+line.pop(0)+")"
  return output

def parse_module(tokens,context):
  module = types.SimpleNamespace()
  module.body = []
  module.functions={}
  module.globals={}
  module.function_types={}
  module.name=""
  linecount=0
  while linecount< len(tokens):
    line=tokens[linecount]
    if line:
      if debug:
        print(line)
      tokenposition=context.tokenpositions[linecount]
      comment = context.comments[linecount]
      if line[0] =="module":
        node=types.SimpleNamespace()
        node.kind="module"
        node.head=""
        if len(line)>1:
          node.head+="(module $"+line[1]
          module.name=line[1]
        if comment:
          node.head+=" ;;"+comment
        module.body.append(node)
      elif line[0] == "func":
        head="(func "
        line.pop(0)
        name=line.pop(0)
        head+="$"+ name
        imported=False
        if "import" in line:
          imported=True
        head+=parse_export_import(line,name)
        locals={}
        params=[]
        results=[]
        if line:
          subtokens,_,_,_=tokenize(line.pop(0))
          while subtokens:
            local = subtokens.pop(0)
            type=parse_type(subtokens.pop(0))
            locals[local] = type
            params.append(type)
            head+="(param $"+local+" "+type.canonical+")"
        if line:
          subtokens,_,_,_=tokenize(line.pop(0))
          if subtokens:
            head+="(result"
          while subtokens:
            type=parse_type(subtokens.pop(0))
            results.append(type)
            head+=" "+type.canonical
            if not subtokens:
              head+=")"
        if comment:
          head+=" ;;"+comment
        body=[]
        if not imported:
          linecount+=1
          start=linecount
          while not tokens[linecount] or tokens[linecount][0]!=")":
            body.append(tokens[linecount])
            linecount+=1
        function = types.SimpleNamespace()
        function.kind="func"
        function.name = name
        function.head = head
        function.locals=locals
        function.results=results
        function.params=params
        function.body=body
        function.tokenpositions=context.tokenpositions[start:linecount]
        function.lines=context.lines[start:linecount]
        function.position=start
        function.comments=context.comments[start:linecount]
        function.indentations=context.indentations[start:linecount]
        module.functions[name]=function
        module.body.append(function)
      elif line[0]=="memory":
        line.pop(0)
        head="(memory"
        head+=parse_export_import(line,"memory")
        head+=" "+line.pop(0)
        if line:
          head+=" "+line.pop(0)
        if line:
          head+=" "+line.pop(0)
        memory = types.SimpleNamespace()
        memory.kind="memory"
        memory.head=head+")"
        module.body.append(memory)
      elif line[0]=="table":
        line.pop(0)
        head="(table"
        head+=" $"+line.pop(0)
        head+=" "+line.pop(0)
        head+=" "+line.pop(0)
        if line:
          head+=" "+line.pop(0)
        table = types.SimpleNamespace()
        table.kind="table"
        table.head=head+")"
        module.body.append(table)
      elif line[0]=="start":
        line.pop(0)
        head="(start $"+line.pop(0)+")"
        start = types.SimpleNamespace()
        start.kind="start"
        start.head=head
        module.body.append(start)
      elif line[0]=="type":
        line.pop(0)
        name = line.pop(0)
        head="(type $"+name+"(func "
        output,function_type= parse_function_type(line)
        module.function_types[name]=function_type
        head+=output+"))"
        type = types.SimpleNamespace()
        type.kind="type"
        type.name=name
        type.head=head
        module.body.append(type)
      elif line[0]=="data":
        line.pop(0)
        head="(data $"+line.pop(0)
        datastring=line.pop(0)
        if datastring[0]=='"':
          head+=" "+datastring+")"
        else:
          head+='"'
          i=0
          while i<len(datastring):
            head+="\\"+datastring[i:i+2]
            i+=2
          head+='")'
        data = types.SimpleNamespace()
        data.kind="data"
        data.head=head
        module.body.append(data)
      elif line[0]=="global":
        line.pop(0)
        head="(global"
        name=line.pop(0)
        head+=" $"+name
        head+=parse_export_import(line,name)
        if line[0]=="mut":
          line.pop(0)
          head+=" mut"
        type=parse_type(line.pop(0))
        module.globals[name]=type
        head+=" "+type.canonical+")"
        globalist = types.SimpleNamespace()
        globalist.kind="global"
        globalist.head=head
        globalist.name=name
        module.body.append(globalist)
      if debug:
        print(module.body[-1].head)
    linecount+=1
  output=""
  for node in module.body:
    output2=""
    if node.kind=="func":
      output2=parse_function_body(node,module)
    output+=node.head+"\n"
    output+=output2
  if module.name:
    output+=")"
  return output


if len(sys.argv) not in {3,4}:
  print("syntax: webassembler.py inputfile [-y] outputfile")
  sys.exit(1)
inputfilename = sys.argv[1]
outputfilename = sys.argv[2]
if sys.argv[2]=="-y":
  outputfilename = sys.argv[3]
elif os.path.isfile(outputfilename):
  print("file exists, not overwriting")
  sys.exit(1)
with open(inputfilename,"r") as f:
  programm = f.read()
lines = programm.split("\n")
tokens=[]
tokenpositions=[]
comments=[]
indentations=[]
for line in lines:
  token,tokenposition,comment,indentation = tokenize(line)
  tokens.append(token)
  tokenpositions.append(tokenposition)
  comments.append(comment)
  indentations.append(indentation)
context = types.SimpleNamespace()
context.lines=lines
context.tokenpositions=tokenpositions
context.comments=comments
context.indentations=indentations
module= parse_module(tokens,context)
if debug:
  print(module)
with open(outputfilename,"w") as f:
  f.write(module)