import struct
import io

class BinaryReader:
    # Map well-known type names into struct format characters.
    typeNames = {
        'bool'   :'?',
        'int8'   :'b',
        'uint8'  :'B',
        'int16'  :'h',
        'uint16' :'H',
        'int32'  :'i',
        'uint32' :'I',
        'int64'  :'q',
        'uint64' :'Q',
        'float'  :'f',
        'double' :'d',
        'char'   :'s'}

    def __init__(self, file, isFile=True):
        if isFile:
            self.stream = open( file, 'br' )
        else:
            self.stream = io.BytesIO( file )

    def readBytes(self, num):
        return self.stream.read(num)

    def readString(self, length):
        value = self.stream.read(length)
        return value.decode('utf-8', 'ignore')
        
    def read(self, typeName):
        typeFormat = BinaryReader.typeNames[typeName.lower()]
        typeSize = struct.calcsize(typeFormat)
        value = self.stream.read(typeSize)
        return struct.unpack(typeFormat, value)[0]

    def seek(self, offset):
        self.stream.seek(offset, 1)

    def goto(self, pos):
        self.stream.seek(pos, 0)

    def getPos(self):
        return self.stream.tell()

    def close(self):
        self.stream.close()

    def __del__(self):
        self.stream.close()

def readBlocks( path ):
    reader = BinaryReader( path )

    #read file header
    fileSize = reader.read('uint32')
    headerVersion = reader.read('uint16')
    version = reader.read('uint16')

    blockOffset = reader.read('uint32')
    blockCount = reader.read('uint32')

    #Seek to the first block
    reader.seek(blockOffset - 8)

    todo = []
    for n in range(blockCount):
        #Read the type (string identifier)
        blockType = reader.readString(4)

        #Offset in the file
        offset = reader.getPos() + reader.read('uint32')

        #Block size
        size = reader.read('uint32')

        todo.append((blockType, offset, size))

    blocks = {}
    for block in todo:
        reader.goto( block[1] )

        name = block[0]

        if name == 'DATA':
            blocks[name] = readBinaryKV3( reader, block[2] )
        elif name == 'VBIB':
            blocks[name] = reader.readBytes( block[2] )
        else:
            blocks[name] = reader.readBytes( block[2] )

    reader.close()

    return blocks

def readBinaryKV3( reader, totalSize ):
    sig = reader.readString(4)
    encoding = reader.readBytes(16)
    kvFormat = reader.readBytes(16)
    flags = reader.readBytes(4)

    endPos = reader.getPos() + totalSize
    out = b''
    outPos = 0

    if (flags[3] & 0x80) > 0:
        out = reader.readBytes( endPos - reader.getPos() )
    else:
        running = True
        while running and reader.getPos() < endPos:
            blockMask = reader.read('uint16')
            for i in range(16):
                if blockMask & (1 << i) > 0:
                    offsetSize = reader.read('uint16')
                    offset = ((offsetSize & 0xFFF0) >> 4) + 1
                    size = (offsetSize & 0x000F) + 3

                    lookupSize = offset if (offset < size) else size

                    readBack = out[-offset:-offset+lookupSize]
                    if lookupSize - offset < 1:
                        readBack = out[-offset:]

                    while size > 0:
                        writeLength = lookupSize if (lookupSize < size) else size
                        size = size - lookupSize
                        out = out + readBack[:writeLength]
                        outPos = outPos + writeLength
                else:
                    data = reader.readBytes(1)
                    out = out + data
                    outPos = outPos + 1

                if outPos >= (flags[2] << 16) + (flags[1] << 8) + flags[0]:
                    running = False
                    break
    return parseBinaryKV3( out )

def parseBinaryKV3( kvBytes ):
    reader = BinaryReader( kvBytes, False )

    #Read all strings
    stringTable = []
    numStrings = reader.read('uint32')

    for _ in range(numStrings):
        stringTable.append( readNullTermString(reader) )

    #Parse the rest
    root = parseNode( reader, None, True, stringTable )
    return root

def parseNode( reader, parent, inArray, stringTable ):
    #Get the name
    name = ''
    if not inArray:
        stringID = reader.read('int32')
        name = stringTable[stringID] if stringID != -1 else ''
    elif parent != None:
        name = len(parent)
        parent.append(0)

    #Read type
    datatype = reader.readBytes(1)[0]
    flags = 0
    if (datatype & 0x80) > 0:
        datatype = datatype & 0x7F
        flags = reader.readBytes(1)[0]

    #Read data
    #NULL
    if datatype == 1:
        parent[name] = None
        pass
    #Boolean
    elif datatype == 2:
        parent[name] = reader.read('bool')
    #Integer
    elif datatype == 3:
        parent[name] = reader.read('int64')
    #Double
    elif datatype == 5:
        parent[name] = reader.read('double')
    #String
    elif datatype == 6:
        stringID = reader.read('int32')
        parent[name] = stringTable[stringID] if stringID != -1 else ''
    #Array
    elif datatype == 8:
        length = reader.read('uint32')
        array = []
        for _ in range(length):
            parseNode( reader, array, True, stringTable )

        parent[name] = array
    #Object
    elif datatype == 9:
        length = reader.read('uint32')
        newObject = {}
        for _ in range(length):
            parseNode( reader, newObject, False, stringTable )

        if parent == None:
            parent = newObject
        else:
            parent[name] = newObject

    return parent

def readNullTermString( reader ):
    string = b''
    c = reader.readBytes(1)
    k = 0
    while c != b'\x00' and k < 100:
        k = k + 1
        string = string + c
        c = reader.readBytes(1)
    return string.decode('utf-8', 'ignore')
