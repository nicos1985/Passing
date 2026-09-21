/* No weak fallback: generated vault passwords require Web Crypto. */
function secureRandomIndex(length) {
    if (!Number.isInteger(length) || length < 1 || length > 65536) {
        throw new Error('Seleccioná al menos un tipo de carácter.');
    }
    const limit = 0x100000000 - (0x100000000 % length);
    const buffer = new Uint32Array(1);
    do { crypto.getRandomValues(buffer); } while (buffer[0] >= limit);
    return buffer[0] % length;
}
