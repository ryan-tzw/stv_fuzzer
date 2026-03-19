grammar ip;

ipAddress
    : ipv6Address
    | ipv4Address
    ;

// IPv4: four octets (0-255) separated by dots.
// Leading zeros are allowed (e.g. 000, 001, 010) up to 3 digits per octet.
ipv4Address
    : ipv4Octet DOT ipv4Octet DOT ipv4Octet DOT ipv4Octet
    ;

// Structurally enforces the 0-255 limit without predicates.
ipv4Octet
    : D2 D5 d0To5                 // 250-255
    | D2 d0To4 decDigit           // 200-249
    | D1 decDigit decDigit        // 100-199
    | D0 decDigit decDigit        // 000-099
    | decDigit decDigit           // 00-99 (2 digits)
    | decDigit                    // 0-9 (1 digit)
    ;

// Parser rules group specific digits together.
decDigit : D0 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 ;
d0To5    : D0 | D1 | D2 | D3 | D4 | D5 ;
d0To4    : D0 | D1 | D2 | D3 | D4 ;

// Combines decimal digits and hex letters at the parser level.
hexChar
    : decDigit
    | HEX_LETTER
    ;

// IPv6 helper rules
h16
    : hexChar hexChar? hexChar? hexChar?
    ;

ls32
    : h16 COLON h16
    | ipv4Address   // allows IPv4-mapped / dual-stack form
    ;

// IPv6 (full, compressed with :: in any position, and dual IPv4-mapped)
ipv6Address
    : h16 (COLON h16)* (COLON ls32)?
    | COLON COLON ( (h16 COLON)* h16 (COLON ls32)? | ls32 )?
    | h16 (COLON h16)* COLON COLON ( (h16 COLON)* h16 (COLON ls32)? | ls32 )?
    ;

// Lexer rules
DOT         : '.' ;
COLON       : ':' ;

// Defining individual digit tokens completely prevents lexer overlap.
D0 : '0' ;
D1 : '1' ;
D2 : '2' ;
D3 : '3' ;
D4 : '4' ;
D5 : '5' ;
D6 : '6' ;
D7 : '7' ;
D8 : '8' ;
D9 : '9' ;

HEX_LETTER  : [a-fA-F] ;

// Optional: ignore whitespace if your input may contain it
WS : [ \t\r\n]+ -> skip ;