grammar json;

json
    : value EOF
    ;

value
    : jsonObject
    | array
    | string
    | number
    | jsonBool
    | nullValue
    ;

jsonObject
    : '{' (member (',' member)*)? '}'
    ;

member
    : string ':' value
    ;

array
    : '[' (value (',' value)*)? ']'
    ;

string
    : STRING
    ;

number
    : NUMBER
    ;

jsonBool
    : TRUE  #trueValue
    | FALSE #falseValue
    ;

nullValue
    : NULL
    ;

STRING
    : '"' (ESC | ~["\\\r\n])* '"'
    ;

fragment ESC
    : '\\' (["\\/bfnrt] | 'u' HEXDIGIT HEXDIGIT HEXDIGIT HEXDIGIT)
    ;

fragment HEXDIGIT
    : [0-9a-fA-F]
    ;

NUMBER
    : '-'? ( '0' | [1-9] [0-9]* ) ( '.' [0-9]+ )? ( [eE] [+-]? [0-9]+ )?
    ;

TRUE  : 'true' ;
FALSE : 'false' ;
NULL  : 'null' ;

WS    : [ \t\r\n]+ -> skip ;