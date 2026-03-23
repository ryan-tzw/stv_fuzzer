grammar ip;

ipExpression
    : ipv4Expression
    | ipv6Expression
    ;

ipv4Expression
    : ipv4Address SLASH prefixV4                                              // CIDR: a.b.c.d/prefix
    | ipv4Address HYPHEN ipv4Address                                          // Full hyphen range: a.b.c.d-w.x.y.z
    | ipv4Address HYPHEN ipv4Octet                                            // Shorthand hyphen: a.b.c.d-z
    | ipv4Address LBRACKET bracketContent RBRACKET                            // Bracket form 1: 192.0.2.8[0-5] or 192.0.2.8[5678]
    | ipv4Octet DOT ipv4Octet DOT ipv4Octet DOT LBRACKET bracketContent RBRACKET // Bracket form 2: 192.0.2.[0-5] or 192.0.2.[5678]
    | ipv4Octet DOT ipv4Octet DOT ipv4Octet DOT ASTERISK                      // Wildcard: a.b.c.*
    | ipv4Address                                                             // Lone IP (Host Route)
    ;

ipv6Expression
    : ipv6Address SLASH prefixV6                                              // CIDR: ipv6/prefix
    | ipv6Address HYPHEN ipv6Address                                          // Full hyphen range: ipv6-ipv6
    | ipv6Address                                                             // Lone IP (Host Route)
    ;

// Structural IPv4 Rules
// IPv4: four octets (0-255) separated by dots.
// Leading zeros are allowed (e.g. 000, 001, 010) up to 3 digits per octet.
ipv4Address
    : ipv4Octet DOT ipv4Octet DOT ipv4Octet DOT ipv4Octet
    ;

ipv4Octet
    : D2 D5 d0To5                 // 250-255
    | D2 d0To4 decDigit           // 200-249
    | D1 decDigit decDigit        // 100-199
    | D0 decDigit decDigit        // 000-099
    | decDigit decDigit           // 00-99 (2 digits)
    | decDigit                    // 0-9 (1 digit)
    ;

prefixV4
    : D0? D3 d0To2                // 030-032, 30-32
    | D0? d0To2 decDigit          // 000-029, 00-29, 10-29
    | decDigit                    // 0-9
    ;

bracketContent
    : ipv4Octet HYPHEN ipv4Octet   // Matches ranges like 0-5 or 10-20
    | decDigit+                    // Matches discrete digit sets like 5678
    ;


// Structural IPv6 Rules
// Structurally enforces 0-128 limit for IPv6 CIDR
prefixV6
    : D0? D1 D2 d0To8             // 0120-0128, 120-128
    | D0? D1 d0To1 decDigit       // 0100-0119, 100-119
    | D0? decDigit decDigit       // 000-099, 00-99
    | decDigit                    // 0-9
    ;

// IPv6 (full, compressed with :: in any position, and dual IPv4-mapped)
ipv6Address
    : h16 (COLON h16)* (COLON ls32)?
    | COLON COLON ( (h16 COLON)* h16 (COLON ls32)? | ls32 )?
    | h16 (COLON h16)* COLON COLON ( (h16 COLON)* h16 (COLON ls32)? | ls32 )?
    ;

h16
    : hexChar hexChar? hexChar? hexChar?
    ;

ls32
    : h16 COLON h16
    | ipv4Address                 // allows IPv4-mapped / dual-stack form
    ;

hexChar
    : decDigit
    | HEX_LETTER
    ;

// Digit Groups (Parser Level)
decDigit : D0 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 ;
d0To8    : D0 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 ;
d0To5    : D0 | D1 | D2 | D3 | D4 | D5 ;
d0To4    : D0 | D1 | D2 | D3 | D4 ;
d0To2    : D0 | D1 | D2 ;
d0To1    : D0 | D1 ;

// Lexer Tokens
SLASH       : '/' ;
HYPHEN      : '-' ;
LBRACKET    : '[' ;
RBRACKET    : ']' ;
ASTERISK    : '*' ;

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