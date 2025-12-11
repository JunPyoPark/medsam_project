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
    const { header, image } = niftiData;
    const dims = header.dims; // [ndim, x, y, z, t, ...]
    const xDim = dims[1];
    const yDim = dims[2];
    const zDim = dims[3];

    let sliceData;
    let width, height;

    // Assuming Int16 or Float32 mostly, but handling generic typed array
    // nifti-reader-js returns ArrayBuffer, we need to view it correctly
    // This part is simplified; robust implementation needs to handle datatype code

    // For MedSAM, we usually deal with 3D volumes.
    // We need to extract the slice.

    // Helper to get typed array based on datatype
    // 2 = uint8, 4 = int16, 16 = float32
    let typedData;
    if (header.datatypeCode === 2) {
        typedData = new Uint8Array(image);
    } else if (header.datatypeCode === 4) {
        typedData = new Int16Array(image);
    } else if (header.datatypeCode === 16) {
        typedData = new Float32Array(image);
    } else {
        // Fallback or error
        typedData = new Uint8Array(image); // dangerous assumption
    }

    if (axis === 'z') {
        width = xDim;
        height = yDim;
        const sliceSize = width * height;
        const offset = sliceIndex * sliceSize;
        sliceData = typedData.slice(offset, offset + sliceSize);
    }

    // Revert to Identity (Raw) as per user request.
    // The user wants the view that results from rotating the previous view (rot90 k=-1) 90 deg left.
    // This implies Identity.

    // Normalize for display (0-255)
    let min = Infinity;
    let max = -Infinity;
    for (let i = 0; i < sliceData.length; i++) {
        if (sliceData[i] < min) min = sliceData[i];
        if (sliceData[i] > max) max = sliceData[i];
    }

    const range = max - min || 1;

    const rgbaData = new Uint8ClampedArray(width * height * 4);
    for (let i = 0; i < sliceData.length; i++) {
        const val = Math.floor(((sliceData[i] - min) / range) * 255);
        rgbaData[i * 4] = val;     // R
        rgbaData[i * 4 + 1] = val; // G
        rgbaData[i * 4 + 2] = val; // B
        rgbaData[i * 4 + 3] = 255; // A
    }

    return new ImageData(rgbaData, width, height);
};
