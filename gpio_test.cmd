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

//Read back id (0xCAFE_BEAF)
ri 0x00020000
s 10

//GPIO5_REG @ 0x0002001A
//DIN OE DS PUD PE   (bit fields)
//0   1  0  0   1    (bit values 0b001_0x01 = 0x11)
//5   4  3  1   0    (bit indices)
wi 0x0002001A 0x00000011
s 10

//DIN_REG @ 0x0002001D (Toggle ON)
//DIN_GPIO5 DIN_GPIO4 DIN_GPIO3 DIN_GPIO2 DIN_GPIO1 DIN_GPIO0 (bit fields)
//1         0         0         0         0         0         (bit values 0b0010_0000 - 0x20)
wi 0x0002001D 0x00000020
s 10
wi 0x0002001D 0x00000000
s 10
wi 0x0002001D 0x00000020


