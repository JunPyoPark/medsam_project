import * as nifti from 'nifti-reader-js';

export const loadNiftiFile = async (file) => {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            try {
                const data = e.target.result;
                if (nifti.isCompressed(data)) {
                    const decompressed = nifti.decompress(data);
                    if (nifti.isNIFTI(decompressed)) {
                        const header = nifti.readHeader(decompressed);
                        const image = nifti.readImage(header, decompressed);
                        resolve({ header, image, data: decompressed });
                    } else {
                        reject(new Error('Not a valid NIfTI file'));
                    }
                } else {
                    if (nifti.isNIFTI(data)) {
                        const header = nifti.readHeader(data);
                        const image = nifti.readImage(header, data);
                        resolve({ header, image, data: data });
                    } else {
                        reject(new Error('Not a valid NIfTI file'));
                    }
                }
            } catch (err) {
                reject(err);
            }
        };
        reader.onerror = (err) => reject(err);
        reader.readAsArrayBuffer(file);
    });
};

export const getSlice = (niftiData, sliceIndex, axis = 'z') => {
    if (!niftiData) {
        return null;
    }
    const { header, image } = niftiData;

    const dims = header.dims;
    const xDim = dims[1];
    const yDim = dims[2];

    let width, height;

    // Create typed view locally (fast, no copy)
    let typedData;
    if (header.datatypeCode === 2) {
        typedData = new Uint8Array(image);
    } else if (header.datatypeCode === 4) {
        typedData = new Int16Array(image);
    } else if (header.datatypeCode === 16) {
        typedData = new Float32Array(image);
    } else {
        typedData = new Uint8Array(image);
    }

    let sliceData;
    if (axis === 'z') {
        width = xDim;
        height = yDim;
        const sliceSize = width * height;
        const offset = sliceIndex * sliceSize;
        // Use subarray for zero-copy view
        sliceData = typedData.subarray(offset, offset + sliceSize);
    }

    // Normalize (O(N))
    let min = Infinity;
    let max = -Infinity;
    for (let i = 0; i < sliceData.length; i++) {
        const val = sliceData[i];
        if (val < min) min = val;
        if (val > max) max = val;
    }

    const range = max - min || 1;

    const rgbaData = new Uint8ClampedArray(width * height * 4);
    const buf32 = new Uint32Array(rgbaData.buffer);

    for (let i = 0; i < sliceData.length; i++) {
        const val = Math.floor(((sliceData[i] - min) / range) * 255);
        // A(255) B(val) G(val) R(val) -> Little Endian
        buf32[i] = (255 << 24) | (val << 16) | (val << 8) | val;
    }

    return new ImageData(rgbaData, width, height);
};

export const getMaskSlice = (niftiData, sliceIndex, axis = 'z') => {
    const { header, image } = niftiData;
    const dims = header.dims;
    const xDim = dims[1];
    const yDim = dims[2];

    let width, height;

    let typedData;
    if (header.datatypeCode === 2) {
        typedData = new Uint8Array(image);
    } else if (header.datatypeCode === 4) {
        typedData = new Int16Array(image);
    } else if (header.datatypeCode === 16) {
        typedData = new Float32Array(image);
    } else {
        typedData = new Uint8Array(image);
    }

    let sliceData;
    if (axis === 'z') {
        width = xDim;
        height = yDim;
        const sliceSize = width * height;
        const offset = sliceIndex * sliceSize;
        sliceData = typedData.subarray(offset, offset + sliceSize);
    }

    const rgbaData = new Uint8ClampedArray(width * height * 4);
    const buf32 = new Uint32Array(rgbaData.buffer);

    const maskColor = (128 << 24) | (0 << 16) | (0 << 8) | 255;
    const transparent = 0;

    for (let i = 0; i < sliceData.length; i++) {
        buf32[i] = sliceData[i] > 0 ? maskColor : transparent;
    }

    return new ImageData(rgbaData, width, height);
};
