op addr data

//set the RESET_N line high
g 0 1

//sleep for 100ms
s 10

//SYSPLL reset
wi 0x00050006 0x00000001
s 10
wi 0x00050006 0x00000000
s 10
wi 0x00050006 0x00000001
s 10

//SYSPLL VCOEN_N, REFCLK_SEL SYSCLK_SEL
wi 0x00050007 0x00000003

ri 0x00050000 0x00000001
