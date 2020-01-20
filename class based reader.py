import io
import struct


BYTE_ORDER = "<"


class Block:
    identifier = ""
    size_bytes = 1
    size_structs = {1: "B", 2: "H"}

    def __init__(self, file):
        assert(file.read(1) == self.identifier)
        self.total_bytes, = struct.unpack("{}{}".format(BYTE_ORDER, self.size_structs[self.size_bytes]),
                                          file.read(self.size_bytes))
        self.data_bytes_remaining = self.total_bytes - 2 - (2 * self.size_bytes)

        self.unpack(file)

        reported_total_bytes, = struct.unpack("{}{}".format(BYTE_ORDER, self.size_structs[self.size_bytes]),
                                              file.read(self.size_bytes))
        assert(reported_total_bytes == self.total_bytes)
        assert(file.read(1) == self.identifier)

    def unpack(self, file):
        pass


class Linecount(Block):
    identifier = b"\x1E"
    size_bytes = 1

    total_lines = "H"
    top_margin = "H"
    top_space = "H"
    bottom_space = "H"
    bottom_margin = "H"
    unknown = b"\xFF\x05\x13"

    def unpack(self, file):
        self.total_lines, = struct.unpack("{}{}".format(BYTE_ORDER, self.total_lines), file.read(2))
        self.top_margin, = struct.unpack("{}{}".format(BYTE_ORDER, self.top_margin), file.read(2))
        self.top_space, = struct.unpack("{}{}".format(BYTE_ORDER, self.top_space), file.read(2))
        self.bottom_space, = struct.unpack("{}{}".format(BYTE_ORDER, self.bottom_space), file.read(2))
        self.bottom_margin, = struct.unpack("{}{}".format(BYTE_ORDER, self.bottom_margin), file.read(2))

        read_unknown = file.read(3)
        if read_unknown != self.unknown:
            print("Format mistake in", self.__class__, "expected unknown of", self.unknown, "read", read_unknown)


class HeaderMargin(Block):
    identifier = b"\x98"
    size_bytes = 1

    left_margin = "H"
    right_margin = "H"
    unknown = b"\x00\x00\x00"
    justification = ";"
    pitch_size = "N"
    line_spacing = "c"

    def unpack(self, file):
        self.left_margin, = struct.unpack("{}{}".format(BYTE_ORDER, self.left_margin), file.read(2))
        self.right_margin, = struct.unpack("{}{}".format(BYTE_ORDER, self.right_margin), file.read(2))
        read_unknown = file.read(3)
        if read_unknown != self.unknown:
            print("Format mistake in", self.__class__, "expected unknown of", self.unknown, "read", read_unknown)
        just_pitch, = file.read(1)
        self.line_spacing, = struct.unpack("{}{}".format(BYTE_ORDER, self.line_spacing), file.read(1))


class Header(Block):
    identifier = b"\x1C"
    size_bytes = 2

    margins = HeaderMargin
    text = "*s"
    newline = b"\x02"

    def unpack(self, file):
        self.margins = self.margins(file)
        self.data_bytes_remaining -= self.margins.total_bytes  # TODO: tracking this is hard to keep up to date
        text_bytes = self.data_bytes_remaining - 1  # newline will take a byte
        self.text, = struct.unpack("{}{}s".format(BYTE_ORDER, text_bytes), file.read(text_bytes))
        assert(file.read(1) == self.newline)


class Footer(Block):
    identifier = b"\x1D"
    size_bytes = 2

    margins = HeaderMargin  # double duty being performed here. Perhaps a better name can be created for this class
    text = "*s"
    newline = b"\x02"

    def unpack(self, file):
        self.margins = self.margins(file)
        self.data_bytes_remaining -= self.margins.total_bytes
        text_bytes = self.data_bytes_remaining - 1  # newline will take a byte
        self.text, = struct.unpack("{}{}s".format(BYTE_ORDER, text_bytes), file.read(text_bytes))
        assert(file.read(1) == self.newline)


class Margin(Block):

    identifier = b"\x98"
    size_bytes = 1

    left_margin = "H"
    right_margin = "H"
    unknown = b"\x00\x00\x06"
    justification = ";"
    pitch_size = "N"
    line_spacing = "c"
    tab_positions = "*H"

    def unpack(self, file):
        self.left_margin, = struct.unpack("{}{}".format(BYTE_ORDER, self.left_margin), file.read(2))
        self.right_margin, = struct.unpack("{}{}".format(BYTE_ORDER, self.right_margin), file.read(2))
        read_unknown = file.read(3)
        if read_unknown != self.unknown:
            print("Format mistake in", self.__class__, "expected unknown of", self.unknown, "read", read_unknown)
        just_pitch, = file.read(1)
        self.line_spacing, = struct.unpack("{}{}".format(BYTE_ORDER, self.line_spacing), file.read(1))

        tab_bytes = self.data_bytes_remaining - 2 - 2 - 3 - 1 - 1
        number_tabs = tab_bytes//2

        self.tab_positions = []
        for tab in range(number_tabs):
            tab_position, = struct.unpack("{}{}".format(BYTE_ORDER, "H"), file.read(2))
            self.tab_positions.append(tab_position)


class WPT(Block):
    identifier = (b"\x8F\x81\x01", b"\xDE")
    size_bytes = 0

    unknown = b"\x07\x00\x00\x42\x52"

    linecount = Linecount
    header = Header
    footer = Footer
    margin = Margin
    body = "*s"

    def __init__(self, file):
        assert(file.read(3) == self.identifier[0])

        read_unknown = file.read(5)
        if read_unknown != self.unknown:
            print("Format mistake in", self.__class__, "expected unknown of", self.unknown, "read", read_unknown)
        self.linecount = self.linecount(file)

        # header and footer are optional blocks, peek to see which if either we have
        next_byte = file.read(1)
        file.seek(-1, io.SEEK_CUR)
        if next_byte == self.header.identifier:
            self.header = self.header(file)
            next_byte = file.read(1)
            file.seek(-1, io.SEEK_CUR)

        if next_byte == self.footer.identifier:
            self.footer = self.footer(file)

        self.margin = self.margin(file)

        self.body = file.read()[:-1].decode("ASCII")  # TODO: LAZY implementation

        file.seek(-1, io.SEEK_CUR)

        read_file_end = file.read(1)
        if read_file_end != self.identifier[1]:
            print("File ends with unexpected byte", read_file_end)


if __name__ == '__main__':
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()

    file_path = filedialog.askopenfilename()
    print(file_path)
    with open(file_path, 'rb') as file_object:
        wpt = WPT(file_object)

    print(wpt.body)

