"""Read only the exact Discord keybinds Local Storage key; never open/write the DB.

LevelDB formats: google/leveldb doc/{log,table}_format.md and db/version_edit.cc.
The on-disk Discord schema is unofficial: unsupported/ambiguous input fails closed.
"""
import ctypes
import ctypes.util
import json
import re
import struct

from .config import DEFAULT, validate

LIMIT = 32 * 1024 * 1024
KEY = b'_https://discord.com\x00\x01keybinds'


def varint(data, pos):
    value = 0
    for shift in range(0, 70, 7):
        if pos >= len(data):
            raise ValueError('Registro incompleto.')
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError('Varint inválido.')


def field(data, pos):
    size, pos = varint(data, pos)
    if size > LIMIT or pos + size > len(data):
        raise ValueError('Campo incompleto.')
    return data[pos:pos + size], pos + size


def _crc_table():
    result = []
    for byte in range(256):
        for _ in range(8):
            byte = (byte >> 1) ^ (0x82f63b78 if byte & 1 else 0)
        result.append(byte)
    return tuple(result)


CRC_TABLE = _crc_table()


def crc32c(data):
    crc = 0xffffffff
    for byte in data:
        crc = CRC_TABLE[(crc ^ byte) & 255] ^ (crc >> 8)
    return crc ^ 0xffffffff


def checked(data, expected):
    crc = crc32c(data)
    masked = (((crc >> 15) | (crc << 17)) + 0xa282ead8) & 0xffffffff
    if masked != expected:
        raise ValueError('Checksum LevelDB inválido; tente novamente com Discord fechado.')


def read_file(path):
    if path.is_symlink() or path.stat().st_size > LIMIT:
        raise ValueError('Arquivo de armazenamento não suportado.')
    return path.read_bytes()


def records(data, allow_tail=False):
    pending = None
    pos = 0
    while pos < len(data):
        remaining = 32768 - pos % 32768
        if remaining < 7:
            pos += remaining
            continue
        if pos + 7 > len(data):
            raise ValueError('Log incompleto; tente com Discord fechado.')
        checksum, size, kind = struct.unpack_from('<IHB', data, pos)
        pos += 7
        if kind == size == checksum == 0:
            pos += remaining - 7
            continue
        if size > remaining - 7 or pos + size > len(data):
            raise ValueError('Log inválido.')
        payload = data[pos:pos + size]
        pos += size
        checked(bytes([kind]) + payload, checksum)
        if kind == 1:
            if pending is not None:
                raise ValueError('Fragmentação inválida.')
            yield payload
        elif kind == 2:
            if pending is not None:
                raise ValueError('Fragmentação inválida.')
            pending = payload
        elif kind in (3, 4) and pending is not None:
            pending += payload
            if len(pending) > LIMIT:
                raise ValueError('Registro grande demais.')
            if kind == 4:
                yield pending
                pending = None
        else:
            raise ValueError('Tipo de log não suportado.')
    if pending is not None:
        raise ValueError('Log incompleto.')


def version(data):
    files, logs = {}, {}
    for edit in records(data):
        pos = 0
        while pos < len(edit):
            tag, pos = varint(edit, pos)
            if tag == 1:
                _, pos = field(edit, pos)
            elif tag in (2, 3, 4, 9):
                logs[tag], pos = varint(edit, pos)
            elif tag == 5:
                _, pos = varint(edit, pos)
                _, pos = field(edit, pos)
            elif tag == 6:
                level, pos = varint(edit, pos)
                number, pos = varint(edit, pos)
                files.pop((level, number), None)
            elif tag == 7:
                level, pos = varint(edit, pos)
                number, pos = varint(edit, pos)
                _, pos = varint(edit, pos)
                _, pos = field(edit, pos)
                _, pos = field(edit, pos)
                files[level, number] = True
            else:
                raise ValueError('Manifest LevelDB não suportado.')
    return {number for _, number in files}, logs.get(2, 0), logs.get(9, 0)


def block_entries(data):
    if len(data) < 4:
        raise ValueError('Bloco incompleto.')
    count = struct.unpack_from('<I', data, len(data) - 4)[0]
    end = len(data) - 4 * (count + 1)
    if count == 0 or end < 0:
        raise ValueError('Bloco inválido.')
    pos, key = 0, b''
    while pos < end:
        shared, pos = varint(data, pos)
        size, pos = varint(data, pos)
        length, pos = varint(data, pos)
        if shared > len(key) or pos + size + length > end:
            raise ValueError('Entrada de bloco inválida.')
        key = key[:shared] + data[pos:pos + size]
        pos += size
        yield key, data[pos:pos + length]
        pos += length


def unpack_block(data, handle):
    offset, pos = varint(handle, 0)
    size, _ = varint(handle, pos)
    if size > LIMIT or offset + size + 5 > len(data):
        raise ValueError('Bloco fora do arquivo.')
    raw = data[offset:offset + size]
    kind = data[offset + size]
    checked(raw + bytes([kind]), struct.unpack_from('<I', data, offset + size + 1)[0])
    if kind == 0:
        return raw
    if kind != 1:
        raise ValueError('Compressão não suportada.')
    library = ctypes.util.find_library('snappy')
    if not library:
        raise ValueError('Importação requer libsnappy (pacote snappy).')
    lib = ctypes.CDLL(library)
    lib.snappy_uncompressed_length.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    lib.snappy_uncompress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
    length = ctypes.c_size_t()
    if lib.snappy_uncompressed_length(raw, len(raw), ctypes.byref(length)) or length.value > LIMIT:
        raise ValueError('Snappy inválido.')
    output = ctypes.create_string_buffer(length.value)
    if lib.snappy_uncompress(raw, len(raw), output, ctypes.byref(length)):
        raise ValueError('Snappy inválido.')
    return output.raw[:length.value]


def table(data):
    if len(data) < 48 or data[-8:] != struct.pack('<Q', 0xdb4775248b80fb57):
        raise ValueError('Tabela LevelDB inválida.')
    footer = data[-48:-8]
    _, pos = varint(footer, 0)
    _, pos = varint(footer, pos)
    for _, handle in block_entries(unpack_block(data, footer[pos:])):
        for key, value in block_entries(unpack_block(data, handle)):
            if len(key) < 8:
                raise ValueError('Chave interna inválida.')
            tag = struct.unpack('<Q', key[-8:])[0]
            yield tag >> 8, tag & 255, key[:-8], value


def batch(data):
    if len(data) < 12:
        raise ValueError('Batch incompleto.')
    sequence, count = struct.unpack_from('<QI', data)
    pos = 12
    for index in range(count):
        if pos >= len(data) or data[pos] not in (0, 1):
            raise ValueError('Batch inválido.')
        kind = data[pos]
        key, pos = field(data, pos + 1)
        value = b''
        if kind == 1:
            value, pos = field(data, pos)
        yield sequence + index, kind, key, value
    if pos != len(data):
        raise ValueError('Batch inválido.')


def read_key(directory):
    current = read_file(directory / 'CURRENT')
    name = current.decode('ascii').strip()
    if not re.fullmatch(r'MANIFEST-\d+', name):
        raise ValueError('Manifest inválido.')
    manifest = read_file(directory / name)
    files, log, previous_log = version(manifest)
    latest = None
    def consider(entries):
        nonlocal latest
        for seq, kind, key, value in entries:
            if key == KEY and (latest is None or seq > latest[0]):
                if kind not in (0, 1):
                    raise ValueError('Tipo de chave não suportado.')
                latest = seq, value if kind else None
    for number in sorted(files):
        path = directory / f'{number:06}.ldb'
        if not path.exists():
            path = directory / f'{number:06}.sst'
        consider(table(read_file(path)))
    for path in sorted(directory.glob('*.log')):
        if path.stem.isdigit() and (int(path.stem) >= log or int(path.stem) == previous_log):
            for item in records(read_file(path), allow_tail=True):
                consider(batch(item))
    if read_file(directory / 'CURRENT') != current or read_file(directory / name) != manifest:
        raise ValueError('Discord atualizou o armazenamento durante a leitura; tente novamente.')
    return latest[1] if latest else None


def profile_from_value(raw):
    if raw is None:
        raise ValueError('Não há atalhos locais salvos no Discord.')
    if not raw or raw[0] not in (0, 1):
        raise ValueError('Codificação Discord desconhecida.')
    value = json.loads(raw[1:].decode('utf-16-le' if raw[0] == 0 else 'latin1'))
    state = value.get('_state', value) if isinstance(value, dict) else None
    if not isinstance(state, dict):
        raise ValueError('Formato de atalhos Discord não suportado.')
    bindings = [b for b in state.values() if isinstance(b, dict) and b.get('action') == 'PUSH_TO_TALK' and b.get('enabled') is True]
    if len(bindings) != 1:
        raise ValueError('É necessário um único atalho Push-to-Talk ativo; use o seletor de botão.')
    shortcut = bindings[0].get('shortcut')
    if not isinstance(shortcut, list) or len(shortcut) != 1:
        raise ValueError('Atalhos combinados não são suportados; use um botão lateral simples.')
    key = shortcut[0]
    if (not isinstance(key, list) or len(key) != 3 or key[0] != 1 or
            type(key[1]) is not int or key[1] not in range(8, 13) or key[2] != '0:0'):
        raise ValueError('Atalho incompatível: suporte automático a Mouse8–Mouse12 em Linux/X11.')
    return validate(DEFAULT | {'linux_button': 275 + key[1] - 8, 'x11_button': key[1]})


def detect(paths):
    directory = paths.config / 'discord/Local Storage/leveldb'
    if not directory.exists():
        raise ValueError('Discord ainda não tem configurações locais neste usuário.')
    return profile_from_value(read_key(directory))
