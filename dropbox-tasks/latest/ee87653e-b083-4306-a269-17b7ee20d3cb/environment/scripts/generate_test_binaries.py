#!/usr/bin/env python3
import os
import shutil
import struct
import subprocess

def compile_base_library():
    print("Compiling base library...")
    cmd = ["g++", "-shared", "-fPIC", "-O2", "libsrc/target_lib.cpp", "-o", "libtarget.so"]
    subprocess.run(cmd, check=True)

def parse_elf_sections(filename):
    with open(filename, 'rb') as f:
        elf_data = f.read()

    # Verify ELF64 Magic
    if elf_data[:4] != b'\x7fELF':
        raise ValueError("Not an ELF file")
    if elf_data[4] != 2:
        raise ValueError("Not a 64-bit ELF file")

    # Read Ehdr fields
    e_shoff = struct.unpack('<Q', elf_data[40:48])[0]
    e_shentsize = struct.unpack('<H', elf_data[58:60])[0]
    e_shnum = struct.unpack('<H', elf_data[60:62])[0]
    e_shstrndx = struct.unpack('<H', elf_data[62:64])[0]

    # Read section headers
    shdrs = []
    for i in range(e_shnum):
        offset = e_shoff + i * e_shentsize
        sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_addralign, sh_entsize = \
            struct.unpack('<IIQQQQIIQQ', elf_data[offset:offset+64])
        shdrs.append({
            'index': i,
            'name_idx': sh_name,
            'type': sh_type,
            'offset': sh_offset,
            'size': sh_size,
            'entsize': sh_entsize,
            'link': sh_link
        })

    # Read shstrtab to get section names
    shstrndx_shdr = shdrs[e_shstrndx]
    shstrtab = elf_data[shstrndx_shdr['offset'] : shstrndx_shdr['offset'] + shstrndx_shdr['size']]

    def get_section_name(name_idx):
        end = shstrtab.find(b'\x00', name_idx)
        if end != -1:
            return shstrtab[name_idx:end].decode('utf-8')
        return ""

    for shdr in shdrs:
        shdr['name'] = get_section_name(shdr['name_idx'])

    return shdrs

def scramble_beta(input_path, output_path):
    print(f"Generating BETA scrambled library: {output_path}")
    shutil.copyfile(input_path, output_path)
    shdrs = parse_elf_sections(output_path)

    with open(output_path, 'r+b') as f:
        for shdr in shdrs:
            if shdr['name'] in ('.rela.dyn', '.rela.plt'):
                f.seek(shdr['offset'])
                relocs_data = f.read(shdr['size'])
                num_entries = shdr['size'] // 24
                
                scrambled_bytes = bytearray()
                for i in range(num_entries):
                    r_offset, r_info, r_addend = struct.unpack('<QQq', relocs_data[i*24:(i+1)*24])
                    
                    r_type = r_info & 0xFFFFFFFF
                    r_sym = r_info >> 32

                    r_sym_scrambled = r_sym ^ 0x2A3B4C5D
                    r_type_scrambled = r_type ^ 0x7E
                    r_info_scrambled = (r_sym_scrambled << 32) | r_type_scrambled

                    scrambled_bytes.extend(struct.pack('<QQq', r_offset, r_info_scrambled, r_addend))
                
                f.seek(shdr['offset'])
                f.write(scrambled_bytes)

def pack_gamma(input_path, output_path):
    print(f"Generating GAMMA packed library: {output_path}")
    shutil.copyfile(input_path, output_path)
    shdrs = parse_elf_sections(output_path)

    with open(output_path, 'r+b') as f:
        for shdr in shdrs:
            if shdr['name'] in ('.rela.dyn', '.rela.plt'):
                if shdr['size'] < 8:
                    continue
                f.seek(shdr['offset'])
                relocs_data = f.read(shdr['size'])
                num_entries = shdr['size'] // 24

                packed_bytes = bytearray()
                # 8-byte header: GMRL magic (0x474D524C), num_entries
                packed_bytes.extend(struct.pack('<II', 0x474D524C, num_entries))

                for i in range(num_entries):
                    r_offset, r_info, r_addend = struct.unpack('<QQq', relocs_data[i*24:(i+1)*24])
                    # Store low 32 bits of r_offset (all .so addresses fit in 32 bits)
                    r_offset_lo = int(r_offset) & 0xFFFFFFFF
                    # r_type fits in 1 byte for all x86-64 reloc types (all < 256)
                    r_type = int(r_info & 0xFF)
                    r_sym = int((r_info >> 32) & 0xFFFFFFFF)
                    # Limit addend to 32-bit signed, sign-extendable on decode
                    addend_32 = struct.unpack('<i', struct.pack('<I', int(r_addend) & 0xFFFFFFFF))[0]

                    # Pack: r_offset_lo32(4) + r_sym(4) + addend(4) + r_type(1) + 3 pad = 16 bytes
                    packed_entry = struct.pack('<IIiB3x', r_offset_lo, r_sym, addend_32, r_type)
                    packed_bytes.extend(packed_entry)

                # Extend with zeroes to match original size
                tail_size = shdr['size'] - len(packed_bytes)
                if tail_size < 0:
                    raise ValueError(f"Packed size for {shdr['name']} exceeds original section size!")
                packed_bytes.extend(b'\x00' * tail_size)

                f.seek(shdr['offset'])

                f.write(packed_bytes)

def main():
    # Make sure output directories exist
    os.makedirs("data/binaries", exist_ok=True)

    compile_base_library()
    
    # Save standard
    shutil.copyfile("libtarget.so", "data/binaries/libtarget_alpha.so")
    
    # Generate scrambled
    scramble_beta("libtarget.so", "data/binaries/libtarget_beta.so")
    pack_gamma("libtarget.so", "data/binaries/libtarget_gamma.so")

    if os.path.exists("libtarget.so"):
        os.remove("libtarget.so")
    print("All test binaries generated successfully!")

if __name__ == "__main__":
    main()
