# Webassembler
Not to be confused with [WebAssembly](https://webassembly.org/)

Webassembler is a simple assembly language purpose-built for writing [WebAssembly](https://webassembly.org/) code.
It targets [WebAssembly text format](https://webassembly.github.io/spec/core/text/index.html) (wat) and aims to have very simmilar syntax, while providing some much-needed syntactic sugar.

The transpiller is written in Python 3, synopsis: `webassembler.py inputfile [-y] outputfile`

Webassembler strives to produce wat output compatible with [wat2wasm](https://github.com/WebAssembly/wabt#running-wat2wasm), however this will not always be the case as wat2wasm is not spec-compliant. Webassembler is not well tested, so expect some bugs.

Webassembler currently implements these [additional WebAssembly features](https://webassembly.org/roadmap/):

[Bulk memory operations](https://github.com/WebAssembly/bulk-memory-operations/blob/master/proposals/bulk-memory-operations/Overview.md) |    [Multi-value](https://github.com/WebAssembly/spec/blob/master/proposals/multi-value/Overview.md)|  [Mutable globals](https://github.com/WebAssembly/mutable-global/blob/master/proposals/mutable-global/Overview.md) | [Reference types](https://github.com/WebAssembly/reference-types/blob/master/proposals/reference-types/Overview.md) | [Non-trapping float-to-int conversions](https://github.com/WebAssembly/spec/blob/master/proposals/nontrapping-float-to-int-conversion/Overview.md) | [Sign-extension operations](https://github.com/WebAssembly/spec/blob/master/proposals/sign-extension-ops/Overview.md) | [Fixed-width SIMD](https://github.com/WebAssembly/simd/blob/master/proposals/simd/SIMD.md) | [Threads and atomics](https://github.com/WebAssembly/threads/blob/master/proposals/threads/Overview.md)

## Examples
Here are some side-by-side comparisons of Webassembler and the equivalent wat it generates:
```
x= a add b
```
```
(local.set $x (local.get $a) (i32.add (local.get $b)))
```
```
[pointer |f32]= div y 2.5
```
```
(f32.store (local.get $pointer) (f32.div(local.get $y) (f32.const 2.5)))
```
Here is a more complex example:
```
s32x test= 1,2,3,4,5,0x6,+7,8 extmul_low s16x -1 mul asi32x f64x not i32x 7
```
```
(local.set $test (v128.const i16x8 1 2 3 4 5 0x6 +7 8) (i32x4.extmul_low_i16x8_s (i16x8.splat (i32.const -1))) (i32x4.mul  (f64x2.convert_low_i32x4_u (v128.not (i32x4.splat (i32.const 7))))))
```
# Syntax

The fundamental element of Webassembler is the word, separated from other words by [ASCII](https://en.wikipedia.org/wiki/ASCII) space, line feed, parentheses `(` `)` or `;`. A word may be a [string](https://webassembly.github.io/spec/core/text/values.html#strings), [identifier](https://webassembly.github.io/spec/core/text/values.html#text-id),[integer](https://webassembly.github.io/spec/core/text/values.html#integers), [floating-point](https://webassembly.github.io/spec/core/text/values.html#floating-point), Webassembler symbol, special instruction/section encoding or part of a comment. Any word that is not a Webassembler symbol or part of a special instruction/section encoding is:

a number, if it starts with a decimal digit `0-9`, a sign `-+` or is a [special floating-point constant](https://webassembly.github.io/spec/core/text/values.html#floating-point),

a string, if it is enclosed by quotes `""` and doesn't contain [certain characters](https://webassembly.github.io/spec/core/text/values.html#strings),

an identifier, if it only contains the ASCII alphabet and [some special characters](https://webassembly.github.io/spec/core/text/values.html#text-id).

part of a comment, if it follows a `;`.

The syntax described here uses standard notation, where an expression in square brackets denotes an optional `[word]` and `|` separates mutually exclusive words. Additionally, `'['` and `']'` are used to represent literal `[` and `]` where necessary.

## Types

`i32`,`i64`,`f32`,`f64`,`ref`,`v128` - these words are the types defined by WebAssembly

`s32`,`s64` - these words are signed types added by Webassembler

`i8x`,`s8x`,`i16x`,`s16x`,`i32x`,`s32x`,`i64x`,`s64x`,`f32x`,`f64x` - these words are vector types added by Webassembler
## Instruction Expressions

An instruction expression is a sequence of instructions, which may be grouped by parentheses to indicate the order of operations. WebAssembly uses a stack-based operand model and all instructions implicitly place their input and output values on this stack. Instructions in an instruction expression are executed from left to right, provided that other instructions from the same expression placed enough values on the stack. If there aren't enough input values on the stack, the instruction will be postponed until further instructions provide enough values. Several instructions may be postponed, in which case the next to execute is always the most recent instruction. There are two exceptions to this: Instructions which write to a variable or memory are always executed after all following instructions. Instructions which consume one input value always take the value from a following instruction, not a preceding one. If there are too many or too few values left on the stack at the end of an instruction expression, then these values will persist across expressions and may also cause some of the above ordering rules to be violated. For this reason it is not recommended to leave values on the stack between instruction expressions.

For example consider the instruction `add`, which takes two inputs and produces one output:
```
add x y
x add y
x y add
```
All of these expressions have the same meaning: add x to y.

Now consider the instruction `neg`, which takes only one input and produces one output:
```
neg add x y
x neg add y
```
All of these expressions mean: add x to y, then negate the result.
```
add neg x y
neg x add y
neg x y add
```
All of these expressions mean: negate x, then add y to the result.
```
add x neg y
x add neg y
x neg y add
```
All of these expressions mean: negate y, then add x to the result.

### Variable Instructions
```
identifier
identifier=
=identifier
global:identifier
global:identifier=
```
Variable instructions read or write values from or to a variable. If the identifier is prefixed or suffixed by `=` then the variable is written to. If the `=` is prefixed then the instruction does not consume its input value from the stack. The identifier may be prefixed with `global:`, in that case it refers to a global variable. The identifier may have at most one of the two prefixes.

### Variable Declarations
`type identifier` - If the first instruction of a line is a type, then it declares the type of the following identifier. As WebAssembly is statically typed, all variables need to be declared before their first use. Note that a declaration does not terminate the instruction expression and may immediately be followed by an assignment to the declared variable.

### Typeconversion Instructions
Any type can occur as an instruction indicating a typeconversion into that type. Note that not all combinations of types can be converted, see the WebAssembly Specification for details. In addition, the instructions `lowx2` and `highx2` will convert a vector to double the elementsize by sign-extending its lower/upper half.

### Typecast Instructions
The instructions `asi`,`asf` and `ass` cast to an integer, float or signed integer of the same size. As these are merely casts, the value is not touched by these instructions and some are even no-ops. There are also casts for all vector types, though not all combinations are valid:
```
asi8x ass8x asi16x ass16x asi32x ass32x asi64x ass64x asf32x asf64x asv128
```
### Automatic Typecasting
Webassembler performs no automatic typecasting for native Webassembly types. However, signed types will cause the results of any instructions they are involved in to become signed as well.


### Immediate Instructions
Immediates are instructions simply producing the number they are denoted by. The type WebAssembly text format is modified slightly to uniquely identify a numbers type. If a number contains a `.` or is a special floating-point value, then it is a floating-point number. If it does not, but is lead by a sign `+-`, then it is signed. If it is trailed by `_`, then it is a 64-bit value, otherwise it is 32-bit.
```
1     ; an i32
+1    ; an s32
-1.0  ; an f32
inf   ; an f32
0xfe  ; an i32
-2_   ; an s64
2._   ; an f64
```
Vector immediates use the same syntax, but chain multiple numbers together using `,`:
```
1,2,3,4           ; an i32x
0,-3,5,2,5,4,3,2  ; an s16x
2.,-4.53          ; an f64x
```
There are also the two reference type immediates `ref.null func` and `ref.null extern`.

## Common Instructions
Most commonly used instructions don't have any special syntax considerations and are simply parsed as part of an instruction expression. As a convenience, a list of ordinary instructions with brief descriptions is provided. Note that these instructions lack any type related information present in WebAssembly text format because Webassembler infers all instruction types. For details on the semantics and valid input types of an instruction refer to the [WebAssembly Specification](https://webassembly.github.io/spec/core/exec/instructions.html)

No inputs:
```
unreachable   ; causes a trap
nop           ; but nothing happened
atomic.fence  ; atomic instructions before the fence complete before atomic instructions after the fence
```
Input `x`:
```
clz          ; count leading 0 digits of the integer x expressed in base 2
ctz          ; count trailing 0 digits of the integer x expressed in base 2
popcnt       ; count the number of 1 digits of the integer/i8vector x expressed in base 2
abs          ; remove the sign of the float/vector x
neg          ; invert the sign of the float/vector x
ceil         ; round the float x towards positive infinity
floor        ; round the float x towards negative infinity
trunc        ; round the float x towards zero
nearest      ; round the float x to the nearest whole number
sqrt         ; square root of the float/floatvector x
eqz          ; 1 if the integer x is 0, 0 otherwise
drop         ; does nothing, but still consumes the input x
ref.is_null  ; 1 if the reference x is null, 0 otherwise
memory.grow  ; grow memory by integer x pages, old size if successful, 0xffffffff otherwise
```
Inputs `x`,`y`:
```
add       ; add x to y
sub       ; subtract y from x
mul       ; multiply x by y
div       ; divide x by y
rem       ; remainder of dividing integers x by y
and       ; bitwise and of integers/vectors x and y
or        ; bitwise or of integers/vectors x and y
xor       ; bitwise xor of integers/vectors x and y
shl       ; bitshift left of integer/integervector x by integer y
shr       ; signed bitshift right of integer/integervector x by integer y
rotl      ; bitrotation left of integer x by integer y
rotr      ; bitrotation right of integer x by integer y
min       ; the minimum of floats/vectors x and y
max       ; the maximum of floats/vectors x and y
copysign  ; copy sign of float y to float x
eq        ; 1 if x is equal to y, 0 otherwise
ne        ; 0 if x is equal to y, 1 otherwise
lt        ; 1 if x is less than y, 0 otherwise
gt        ; 1 if x is greater than y, 0 otherwise
le        ; 1 if x is less than or equal to y, 0 otherwise
ge        ; 1 if x is greater than or equal to y, 0 otherwise
```
Inputs `x`,`y`,`z`:
```
select       ; x if integer z is not zero, y otherwise
memory.fill  ; set all bytes between address x and x+z to y
memory.copy  ; copy z bytes from address y to address x
```
Vector input `x`:
```
not              ; bitwise not of x
any_true         ; 0 if the entire vector is zero, 1 otherwise
all_true         ; 0 if any element of the integervector x is 0, 1 otherwise
bitmask          ; an integer, whose n-th bit is zero if the n-th element of the integervector x is zero
extadd_pairwise  ; pairwise add the elements of x and double the elementsize
```
Vector inputs `x`,`y`:
```
swizzle      ; all 16 elements of x are replaced by an element of x indicated by the indices in y
andnot       ; bitwise and of x and bitwise not of y
narrow       ; integervectors x is concatenated to y by halfing the size of all elements 
add_sat      ; elementwise add integervectors x to y, overflows are clamped
sub_sat      ; elementwise subtract integervectors y from x, underflows are clamped
dot          ; refer to the spec
extmul_low   ; multiply lower halves of integervectors x and y, elementsize is doubled
extmul_high  ; multiply upper halves of integervectors x and y, elementsize is doubled
avgr         ; elementwise average of integervectors x and y
q15mulr_sat  ; elementwise fixed-point multiply of integervectors x by y, the point is before bit 15
pmin         ; elementwise minimum of floatvectors x and y; slightly different definition than min
pmax         ; elementwise maximum of floatvectors x and y; slightly different definition than max
```
Vector inputs `x`,`y`,`z`:
```
bitselect  ; bitwise select
```
### Immediate Instructions
Some instructions are immediately followed by a static identifier indicating the table/data they operate on.

No inputs:
```
data.drop   ; deletes the data section
table.size  ; the number of references in the table
```
Integer input `x`:
```
table.get  ; reference at index x 
```
Inputs `x`,`y`:
```
table.set   ; set reference at table index y to x
table.grow  ; append y new references with value x to the table
```

Inputs `x`,`y`,`z`:
```
memory.init  ; copy z bytes from offset y of the data section to address x
table.fill   ; set z entries of the table to reference y, starting at x
table.copy   ; copy z entries from offset y of table2 to offset x of table1
```


## Memory Access Instructions
Memory access instructions use a special syntax to encode the multitude of possible operations. They always start with `[` and end with either `]` to indicate a load or `]=` to indicate a store.
```
'['instruction expression [integer][,memorytype][,integer]']'[=]
```
The instruction expression has to evaluate to the address of the memory access. The first integer is a constant offset to add to the address. The memorytype specifies the type to load as any ordinary type or one of many special memory types. The second integer specifies the alignment of the address, which may be no larger than the size of the memorytype.

### Special Memory Types
```
i8 s8 i16 s16
```
These types indicate an 8/16-bit load, which is sign-extended to 32 bits.
```
i8i64 s8s64 i16i64 s16s64 i32i64 s32s64
```
These types indicate an 8/16/32-bit load, which is sign-extended to 64 bits. Additionally, there are some special memory types for writes:
```
low8 low16 low32
```
These types indicate a write of only the low 8/16/32 bits to memory.
### Atomics
```
atomic
```
This type indicates an atomic read/write. It may be suffixed with any of the non-atomic non-vector special memory types (for example `atomici8i64`). There are also a number of other atomic operations, which can be performed during a memory access:
```
aadd asub aor axor aand xchg cmpxchg
```
These may be suffixed with a special memory write type (for example `axorlow8`). In addition, there are two special atomic operations:
```
wait notify
```
These are never suffixed.
### Vector Memorytypes
In addition to the ordinary vectortypes, a vector may also load/store only a single element.
```
'['integer']'[=]
```
The integer indicates the index of the element to load/store.

## Control Flow Instructions
Structured control flow instructions occupy an entire line with the exception of `end`, which may be followed by more `end` instructions.
Webassembler features two structured control flow instructions, `if` and `loop`. They can be nested and must always be concluded by a matching `end` instruction.
```
loop identifier
[instruction expression]...
end
```
Unlike in WebAssembly, a loop always repeats the contained instructions until broken by explicit control flow.
```
if [instruction expression]
[instruction expression]...
[else [if [instruction expression]]]
[instruction expression]...
end [identifier] [end [identifier]]
```
The optional instruction expression immediately following an `if` instruction specifies the condition. Additionally, an `if` instruction may contain an `else` instruction, which may contain a nested `if` instruction on the same line. The optional identifier following an `end` instruction indicates a label, that can be jumped to from within the `if` instruction. If the `if` instruction has no corresponding `else` instruction, then the values on the stack must be the same before and after the `if` body. If the `if` instruction has a corresponding `else` instruction, then both instruction sequences must consume/produce the same values on the stack.
### Labels
```
identifier:
```
A label denotes a position in the code and occupies an entire line.
### Branch Instructions
```
br identifier
br_if identifier
br_table identifier[,identifier]... identifier
```
Branches jump to a label indicated by an identifier. As WebAssembly only features structured control flow, branches may only jump to labels following the branch and it is impossible to jump into the body of a structured control flow instruction. Any values on the stack at the location of a branch instruction must be the same at the location of any of its target labels. The `br_table` instruction uses an input value to determine the index of a label within its table to jump to; the last identifier indicates the default label in case the value is out of bounds.

### Call Instructions
```
call identifier
call_indirect identifier identifier|[([type]...)] [([type]...)]
return
```
A call instruction executes the function identified by the first identifier and consumes and produces values on the stack according to its signature. Indirect calls specify a `table` with their first identifier, which is indexed to determine the called function dynamically. Indirect calls must statically specify the function signature, either as an inline declaration or by referencing one of the modules `type` sections by identifier. The `return` instruction always returns all values on the stack from the current function.

## Special Vector Instructions
```
shuffle integer,integer,integer,integer,integer,integer,integer,integer,integer,integer,integer,integer,integer,integer,integer,integer
```
The vector instruction `shuffle` is followed by 16 integer indices between 0 and 31. Each corresponds to an element in the 16 element result vector and indicates an element from one of two concatenated input vectors.
### Vector Element Instructions
```
x'['integer']'[=]
```
The integer indicates the index of the element of the vector to access. If the `=` is present, then the element is replaced with an input value, otherwise its value is the result.



## Module
A Webassembler module is made up of an optional header followed by other sections in any order.
Each section must begin at the start of a line.

### Import&Export
Some sections can be imported or exported, in this case they feature an `import&export` expression:
```
[export [string ]... ][import [string ][string ]]
```
The strings specify the name of the imported/exported section. If the export string is missing, then it is replaced by the sections identifier. If one import string is missing, then it is the second string and replaced by the sections identifier, if both import strings are missing, then the first one is `"global"` and the second is replaced by the sections identifier.

### Header
 `[module [identifier]]` - optional header, the identifier only serves as metadata

### Memory 
`memory [import&export] integer [integer] [shared]` - the integers are the initial and maximum size of the memory.

### Data
`data identifier string|rawhex` - rawhex is any sequence of hexadecimal digits.

### Table
`table identifier integer [integer] funcref|externref` - the integers are the initial and maximum size of the table.

### Global
`global identifier [import&export] [mut] type` - declares a global variable with name identifier.

### Type
`type identifier [([type]...)] [([type]...)]` - specifies the function signature named identifier.

### Func
```
func identifier [import&export] [([identifier type]...)] [([type]...)]
[instruction expression]...
[)]
```
Specifies the function named identifier with the given type signature and a sequence of instruction expressions on the following lines terminated by a `)`, unless it is imported.

### Start
`start identifier` - specifies the modules start function.
