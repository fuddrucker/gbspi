import pathlib
import sys
import re
import time

import ft4222
import argparse
import enum


class FTDI4222DK:
    MASTER_DESC = b'FT4222 A'
    GPIO_DESC = b'FT4222 B'
    LOCATION_IDX = 'location'

    def __init__(self):
        self.dev_master: ft4222.FT4222 = None
        self.dev_gpio: ft4222.FT4222 = None
        self.ft_master_devs = []
        self.ft_gpio_devs = []

    def __del__(self):
        try:
            if self.dev_gpio is not None:
                self.dev_gpio.close()

            if self.dev_master is not None:
                self.dev_master.chipReset()
                self.dev_master.close()
        except ft4222.FT2XXDeviceError as e:
            print('can\'t close ft4222: ' + e.__str__())

    def list_dev(self, print_list=False):
        self.ft_master_devs = []
        self.ft_gpio_devs = []
        nb_dev = ft4222.createDeviceInfoList()

        if print_list:
            print('nb of FTDI devices: {}'.format(nb_dev))

        if nb_dev <= 0:
            if print_list:
                print('no devices found...')
            sys.exit(0)

        if print_list:
            print("devices:")
        for i in range(nb_dev):
            detail = ft4222.getDeviceInfoDetail(i, True)
            if detail['description'] == self.MASTER_DESC:
                self.ft_master_devs.append(detail)
            else:
                self.ft_gpio_devs.append(detail)

        if print_list:
            print('Master Devices (SPI)')
            for master_detail in self.ft_master_devs:
                print(master_detail)
            print('GPIO Devices')
            for gpio_detail in self.ft_gpio_devs:
                print(gpio_detail)

    def open_interfaces(self, spi_idx, gpio_idx):
        self.list_dev()
        if spi_idx >= len(self.ft_master_devs):
            print('spi device index out of range -- board not connected?')
            raise IndexError('spi idx out of range')

        if gpio_idx >= len(self.ft_gpio_devs):
            print('gpio device index out of range -- board not connected?')
            raise IndexError('gpio idx out of range')

        try:
            self.dev_master = ft4222.openByLocation(self.ft_master_devs[spi_idx][self.LOCATION_IDX])
            self.dev_master.setClock(ft4222.SysClock.CLK_24)
            self.dev_master.spiMaster_Init(ft4222.Mode.SINGLE, ft4222.Clock.DIV_512, ft4222.Cpol.IDLE_LOW,
                                           ft4222.Cpha.CLK_TRAILING, ft4222.SlaveSelect.SS0)
            self.dev_master.setTimeouts(500, 500)
        except ft4222.FT2XXDeviceError as e:
            print('cant open SPI Interface: ' + e.__str__())

        try:
            self.dev_gpio = ft4222.openByLocation(self.ft_gpio_devs[gpio_idx][self.LOCATION_IDX])
            self.dev_gpio.gpio_Init(gpio0=ft4222.Dir.OUTPUT)
        except ft4222.FT2XXDeviceError as e:
            print('cant open GPIO Interface: ' + e.__str__())

        if self.dev_gpio is None or self.dev_master is None:
            print('could not initialize FTDI 4222')
            raise IOError('could not open F4222')


class GBProto:
    OPCODE_BUS_WRITE = 0x1F
    OPCODE_BUS_READ = 0x30
    OPCODE_GET_BUS_DATA = 0x50
    OPCODE_SET_BUS_DATA = 0x60
    OPCODE_SET_ADDR = 0xA0

    def __init__(self, ftdidk: FTDI4222DK):
        self._ftdidk = ftdidk

    def set_addr(self, addr):
        return self._ftdidk.dev_master.spiMaster_SingleWrite(b''.join([bytes([self.OPCODE_SET_ADDR]), addr]), True)

    def bus_read(self):
        return self._ftdidk.dev_master.spiMaster_SingleWrite(bytes([self.OPCODE_BUS_READ, 0x00, 0x00, 0x00, 0x00]),
                                                             True)

    def bus_write(self):
        return self._ftdidk.dev_master.spiMaster_SingleWrite(bytes([self.OPCODE_BUS_WRITE, 0x00, 0x00, 0x00, 0x00]),
                                                             True)

    def set_data(self, data):
        return self._ftdidk.dev_master.spiMaster_SingleWrite(b''.join([bytes([self.OPCODE_SET_BUS_DATA]), data]), True)

    def get_data(self):
        return self._ftdidk.dev_master.spiMaster_SingleReadWrite(bytes([self.OPCODE_GET_BUS_DATA, 0x00, 0x00, 0x00, 0x00]), True)

    def read_int(self, addr):
        self.set_addr(addr)
        self.bus_read()
        return self.get_data()

    def write_int(self, addr, data):
        self.set_addr(addr)
        self.set_data(data)
        self.bus_write()

    def set_gpio(self, addr, data):
        self._ftdidk.dev_gpio.gpio_Write(ft4222.Port.P0, bool(data))



class CommandType(enum.Enum):
    SLEEP = 1
    GPIO = 2
    WRITE = 3
    READ = 4
    UNKNOWN = 5


class Command:
    FIELD_OPERATION = 'op'
    FIELD_ADDR = 'addr'
    FIELD_DATA = 'data'

    OP_SLEEP = 's'
    OP_GPIO = 'g'
    OP_WRITE = 'wi'
    OP_READ = 'ri'

    def __init__(self, cmd_dict):
        match cmd_dict[self.FIELD_OPERATION]:
            case self.OP_SLEEP:
                self._type = CommandType.SLEEP
                self._data = cmd_dict[self.FIELD_ADDR]
            case self.OP_GPIO:
                self._type = CommandType.GPIO
                self._addr = cmd_dict[self.FIELD_ADDR]
                self._data = cmd_dict[self.FIELD_DATA]
            case self.OP_WRITE:
                self._type = CommandType.WRITE
                self._addr = bytes([(int(cmd_dict[self.FIELD_ADDR], 16) >> i & 0xFF) for i in (24, 16, 8, 0)])
                self._data = bytes([(int(cmd_dict[self.FIELD_DATA], 16) >> i & 0xFF) for i in (24, 16, 8, 0)])
            case self.OP_READ:
                self._type = CommandType.READ
                self._addr = bytes([(int(cmd_dict[self.FIELD_ADDR], 16) >> i & 0xFF) for i in (24, 16, 8, 0)])
            case _:
                print('?')

    def get_type(self):
        return self._type

    def get_addr(self):
        return self._addr

    def get_data(self):
        return self._data


class CommandIterator:
    ''' Iterator class '''

    def __init__(self, commandparser):
        self._commandparser = commandparser
        self._index = 0

    def __next__(self):
        ''''Returns the next value from team object's lists '''
        if self._index < (len(self._commandparser.commands)):
            result = self._commandparser.commands[self._index]
            self._index += 1
            return result
        # End of Iteration
        raise StopIteration


class CommandParser:

    def __init__(self, cmd_path):
        rex = re.compile(r'\W+')
        self.commands = []
        with open(cmd_path) as f_cmds:
            lines = f_cmds.readlines()
            line_idx = 0
            for real_line_idx, line in enumerate(lines):
                line = line.strip()
                if line.startswith('//') or line.startswith('#'):
                    continue
                line = rex.sub(' ', line)
                if not line:
                    continue
                else:
                    if line_idx == 0:
                        cols = [item.strip() for item in line.split(' ')]
                        line_idx = line_idx + 1
                    else:
                        cmd_dict = {}
                        cmd_vals = [item.strip() for item in line.split(' ')]
                        for cmd_idx, cmd_val in enumerate(cmd_vals):
                            try:
                                cmd_dict[cols[cmd_idx]] = cmd_vals[cmd_idx]
                            except IndexError as e:
                                print('malformed line in cmd file -- extra command? ')
                                print(len(line.split(' ')).__str__() + ' commands given, but ' + len(cols).__str__() +
                                      ' expected')
                                print('line ' + (real_line_idx + 1).__str__() + ': \'' + line + '\'')
                                print('cmds: ' + cols.__str__())
                        self.commands.append(Command(cmd_dict))

    def __iter__(self):
        return CommandIterator(self)


class CommandRunner:
    FIELD_OPERATION = 'op'
    FIELD_ADDR = 'addr'
    FIELD_DATA = 'data'

    OP_SLEEP = 's'
    OP_GPIO = 'g'
    OP_WRITE = 'wi'
    OP_READ = 'ri'

    def __init__(self, ftdidk, commands):
        self._commands = commands
        self._ftdidk = ftdidk
        self._GBProto = GBProto(ftdidk)

    def run(self):
        for idx, command in enumerate(self._commands):
            match command.get_type():
                case CommandType.SLEEP:
                    stime = int(command.get_data())
                    time.sleep(stime/1000)
                case CommandType.GPIO:
                    addr = command.get_addr()
                    data = command.get_data()
                    self._GBProto.set_gpio(addr, data)
                case CommandType.WRITE:
                    addr = command.get_addr()
                    data = command.get_data()
                    self._GBProto.write_int(addr, data)
                case CommandType.READ:
                    addr = command.get_addr()
                    print(self._GBProto.read_int(addr))

                case _:
                    print('?')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('cmds', metavar='path', help='path to the command file', type=pathlib.Path)
    args = vars(parser.parse_args())

    ftdidk = FTDI4222DK()
    ftdidk.open_interfaces(spi_idx=0, gpio_idx=0)

    commands = CommandParser(args['cmds'])

    CommandRunner(ftdidk, commands).run()


if __name__ == "__main__":
    main()
