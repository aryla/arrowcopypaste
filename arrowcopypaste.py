#!/usr/bin/env python3

import base64
import struct


_TEMPO_MAGIC = 'ArrowVortex:tempo:'
_NOTES_MAGIC = 'ArrowVortex:notes:'


class Note:
    """
    A single note

    Attributes
    ----------
    start : int
        Start tick

    end : int
        End tick

    column : int
        Column

    special : int
        A value that indicates the note type
    """

    def __init__(self, start, end, column, special):
        self.start = start
        self.end = end
        self.column = column
        self.special = special

    def is_step(self):
        return self.special <= 0 and self.start == self.end

    def is_mine(self):
        return self.special == 1 and self.start == self.end

    def is_lift(self):
        return self.special == 3 and self.start == self.end

    def is_fake(self):
        return self.special == 4 and self.start == self.end

    def is_hold(self):
        return self.special == 0 and self.start != self.end

    def is_roll(self):
        return self.special != 0 and self.start != self.end

    @staticmethod
    def make_step(tick, column):
        """
        Create a normal note.

        Examples
        --------
        >>> n = Note.make_step(32, 0)
        >>> n.is_step()
        True
        """
        return Note(tick, tick, column, -1)

    @staticmethod
    def make_mine(tick, column):
        """
        Create a mine.

        Examples
        --------
        >>> n = Note.make_mine(16, 2)
        >>> n.is_mine()
        True
        """
        return Note(tick, tick, column, 1)

    @staticmethod
    def make_lift(tick, column):
        """
        Create a lift note.

        Examples
        --------
        >>> n = Note.make_lift(8, 0)
        >>> n.is_lift()
        True
        """
        return Note(tick, tick, column, 3)

    @staticmethod
    def make_fake(tick, column):
        """
        Create a fake note.

        Examples
        --------
        >>> n = Note.make_fake(0, 3)
        >>> n.is_fake()
        True
        """
        return Note(tick, tick, column, 4)

    @staticmethod
    def make_hold(start, end, column):
        """
        Create a hold note.

        Examples
        --------
        >>> n = Note.make_hold(0, 64, 2)
        >>> n.is_hold()
        True
        """
        return Note(start, end, column, 0)

    @staticmethod
    def make_roll(start, end, column):
        """
        Create a roll note.

        Examples
        --------
        >>> n = Note.make_roll(8, 16, 0)
        >>> n.is_roll()
        True
        """
        return Note(start, end, column, 2)

    def __repr__(self):
        return 'Note(start={}, end={}, column={}, special={})'.format(
            self.start, self.end, self.column, self.special)


def tempo_to_clipboard_data(bpms, stops):
    """
    Parameters
    ----------
    bpms : [(int, float)]
        List of tuples where the first element is the tick and the second
        element is the new tempo in beats per minute.
    stops : [(int, float)]
        List of tuples where the first element is the tick and the second
        element is the length of the stop in seconds.

    Returns
    -------
    str
        Encoded data.

    Examples
    --------
    >>> bpms = [(0, 120.0), (48, 180.0), (96, 240.0)]
    >>> stops = [(24, 0.5), (72, 2.0)]
    >>> tempo_to_clipboard_data(bpms, stops)
    'ArrowVortex:tempo:!rr<$zz?9g1Ez!!!"LAjB`(zzDEn7((]XO9z!!(qA8,rViz!!!!a!!'
    """
    # Sort by tick.
    bpms = sorted(bpms, key=lambda x: x[0])
    stops = sorted(stops, key=lambda x: x[0])

    blocks = []

    def pack_tempo_block(data, type):
        nonlocal blocks
        blocks.append(struct.pack('<B', len(data)))
        blocks.append(struct.pack('<B', type))
        for item in data:
            blocks.append(struct.pack('<I', item[0]))
            blocks.append(struct.pack('<d', item[1]))

    for i in range(0, len(bpms), 254):
        pack_tempo_block(bpms[i:i+254], type=0)

    for i in range(0, len(stops), 254):
        pack_tempo_block(stops[i:i+254], type=1)

    blocks.append(struct.pack('<B', 0))

    encoded = base64.a85encode(b''.join(blocks)).decode('ascii')
    return _TEMPO_MAGIC + encoded


def clipboard_data_to_tempo(data):
    """
    Parameters
    ----------
    data : str
        Encoded data.

    Returns
    -------
    [(int, float)]
        List of tuples where the first element is the tick and the second
        element is the new tempo in beats per minute.
    [(int, float)]
        List of tuples where the first element is the tick and the second
        element is the length of the stop in seconds.

    Examples
    --------
    >>> data = 'ArrowVortex:tempo:!rr<$zz?9g1Ez!!!"LAjB`(zzDEn7((]XO9z!!(qA8,rViz!!!!a!!'
    >>> bpms, stops = clipboard_data_to_tempo(data)
    >>> bpms
    [(0, 120.0), (48, 180.0), (96, 240.0)]
    >>> stops
    [(24, 0.5), (72, 2.0)]
    """
    if not data.startswith(_TEMPO_MAGIC):
        raise ValueError('Invalid data')

    data = base64.a85decode(data[len(_TEMPO_MAGIC):])
    offset = 0

    def unpack(format):
        nonlocal data
        nonlocal offset
        size = struct.calcsize(format)
        if offset + size > len(data):
            raise ValueError()
        result = struct.unpack_from(format, data, offset)
        offset += size
        return result

    bpms = []
    stops = []

    while True:
        count = unpack('<B')[0]
        if count == 0:
            break

        type = unpack('<B')[0]

        for _ in range(count):
            tick = unpack('<I')[0]
            value = unpack('<d')[0]
            item = (tick, value)

            if type == 0:
                bpms.append(item)
            elif type == 1:
                stops.append(item)
            else:
                raise ValueError()

    return bpms, stops


def notes_to_clipboard_data(notes):
    """
    Parameters
    ----------
    notes : [Note]
        List of notes.

    Returns
    -------
    str
        Encoded data.

    Examples
    --------
    >>> notes = [
    ...     Note.make_step(0, 0),
    ...     Note.make_hold(0, 24, 3),
    ...     Note.make_roll(12, 24, 1),
    ... ]
    >>> notes_to_clipboard_data(notes)
    'ArrowVortex:notes:!!<3$K)c_gJIE@s'
    """
    def pack_vlc(value):
        done = False
        while not done:
            byte = value & 0x7f
            value = value >> 7
            done = value == 0
            if not done:
                byte = byte | 0x80
            yield struct.pack('<B', byte)

    data = []
    data.append(struct.pack('<B', 0))
    data.extend(pack_vlc(len(notes)))

    for note in notes:
        if note.is_step():
            data.append(struct.pack('<B', note.column & 0x7f))
            data.extend(pack_vlc(note.start))
        else:
            data.append(struct.pack('<B', note.column | 0x80))
            data.extend(pack_vlc(note.start))
            data.extend(pack_vlc(note.end))
            data.append(struct.pack('<B', note.special))

    encoded = base64.a85encode(b''.join(data)).decode('ascii')
    return _NOTES_MAGIC + encoded


def clipboard_data_to_notes(data):
    """
    Parameters
    ----------
    data : str
        Encoded data.

    Returns
    -------
    [Note]
        List of notes.

    Examples
    --------
    >>> data = 'ArrowVortex:notes:!!<3$K)c_gJIE@s'
    >>> notes = clipboard_data_to_notes(data)
    >>> len(notes)
    3
    >>> notes[0]
    Note(start=0, end=0, column=0, special=-1)
    >>> notes[1]
    Note(start=0, end=24, column=3, special=0)
    >>> notes[2]
    Note(start=12, end=24, column=1, special=2)
    """
    if not data.startswith(_NOTES_MAGIC):
        raise ValueError('Invalid data')

    data = base64.a85decode(data[len(_NOTES_MAGIC):])
    offset = 0

    def unpack(format):
        nonlocal data
        nonlocal offset
        size = struct.calcsize(format)
        if offset + size > len(data):
            raise ValueError()
        result = struct.unpack_from(format, data, offset)
        offset += size
        return result

    def unpack_vlc():
        value = 0
        num_bytes = 0
        last = False
        while not last:
            byte = unpack('<B')[0]
            last = (byte & 0x80) == 0
            value = value | ((byte & 0x7f) << (7 * num_bytes))
            num_bytes += 1
        return value

    notes = []

    head = unpack('<B')[0]
    count = unpack_vlc()

    for _ in range(count):
        bits = unpack('<B')[0]
        is_long_format = bits & 0x80 != 0
        column = bits & 0x7f

        if is_long_format:
            start = unpack_vlc()
            end = unpack_vlc()
            special = unpack('<B')[0]
        else:
            special = -1
            start = end = unpack_vlc()

        notes.append(Note(start, end, column, special))

    return notes


if __name__ == '__main__':
    import doctest
    doctest.testmod()
