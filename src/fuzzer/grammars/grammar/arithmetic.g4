grammar arithmetic;

// Entry point
expr: term ((PLUS | MINUS) term)*;

term: factor ((MULT | DIV) factor)*;

factor: NUMBER | LPAREN expr RPAREN;

// Tokens
PLUS: '+';
MINUS: '-';
MULT: '*';
DIV: '/';
LPAREN: '(';
RPAREN: ')';
NUMBER: [0-9]+;
WS: [ \t\r\n]+ -> skip;
