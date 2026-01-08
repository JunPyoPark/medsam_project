import * as nifti from 'nifti-reader-js';

let niftiHeader = null;
let niftiImage = null;
let maskHeader = null;
let maskImage = null;
let mergedVolume = null; // Cache for the entire merged RGBA volume

self.onmessage = async (e) => {
    const { type, payload } = e.data;

    if (type === 'LOAD_IMAGE') {
        const { data } = payload;
        try {
            if (nifti.isCompressed(data)) {
                const decompressed = nifti.decompress(data);
                if (nifti.isNIFTI(decompressed)) {
                    niftiHeader = nifti.readHeader(decompressed);
                    niftiImage = nifti.readImage(niftiHeader, decompressed);
                    mergedVolume = null; // Reset cache

                    // Sanitize header to remove functions (DataCloneError fix)
                    const safeHeader = JSON.parse(JSON.stringify(niftiHeader));
                    self.postMessage({ type: 'IMAGE_LOADED', payload: { header: safeHeader } });
                }
            } else {
                if (nifti.isNIFTI(data)) {
                    niftiHeader = nifti.readHeader(data);
                    niftiImage = nifti.readImage(niftiHeader, data);
                    mergedVolume = null; // Reset cache

                    const safeHeader = JSON.parse(JSON.stringify(niftiHeader));
                    self.postMessage({ type: 'IMAGE_LOADED', payload: { header: safeHeader } });
                } else {
                    self.postMessage({ type: 'ERROR', payload: "Data is not NIfTI" });
                }
            }
        } catch (err) {
            self.postMessage({ type: 'ERROR', payload: err.message });
        }
    } else if (type === 'LOAD_MASK') {
        const { header, image } = payload;
        maskHeader = header;
        maskImage = image;

        // Pre-calculate the entire merged volume here (User's request for "Single File" speed)
        try {
            if (niftiHeader && niftiImage) {
                mergedVolume = preCalculateMergedVolume(niftiHeader, niftiImage, maskHeader, maskImage);
            }
            self.postMessage({ type: 'MASK_LOADED' });
        } catch (err) {
            console.error("Pre-calculation failed", err);
            // Fallback to on-the-fly if memory fails? For now just report
            self.postMessage({ type: 'ERROR', payload: "Failed to merge volumes: " + err.message });
        }

    } else if (type === 'GET_SLICE') {
        const { sliceIndex } = payload;
        if (!niftiHeader || !niftiImage) return;

        try {
            let bitmap;

            if (mergedVolume) {
                // Super fast path: Slice from pre-calculated volume
                // Note: Merged volume pre-calc currently bakes in normalization. 
                // If we want dynamic WW/WL on merged volume, we need to re-calc or adjust shader.
                // For now, let's fallback to generateSliceBitmap if not auto, OR update generateBitmapFromCache?
                // Actually, mergedVolume logic in preCalculateMergedVolume uses min/max of the WHOLE volume.
                // If we want per-slice WW/WL or dynamic, we should probably not use the baked mergedVolume for the base layer,
                // OR we need to re-generate the base layer part.

                // For simplicity and correctness with WW/WL, let's use the standard path if we are not in default auto mode,
                // OR just use generateSliceBitmap for the base layer always and overlay mask separately?
                // The current architecture returns baseBitmap and maskBitmap separately in the non-merged path?
                // Wait, generateSliceBitmap returns just the base image.
                // The GET_SLICE handler returns { baseBitmap, maskBitmap }.
                // If mergedVolume is used, it returns ONE bitmap with both?
                // Let's check generateBitmapFromCache.

                // generateBitmapFromCache returns a single bitmap from the merged volume.
                // If we want to support WW/WL, we can't use the pre-baked merged volume easily without re-baking.
                // Re-baking whole volume on every WW/WL change is too slow.
                // So, if we are changing WW/WL, we should probably use the per-slice generation.

                // Let's force the dynamic path if we are not in the initial state?
                // Or better, let's just use generateSliceBitmap which is fast enough for 2D slice viewing.
                // The "mergedVolume" optimization was for "Single File" speed, likely for 3D or scrolling.

                // For this task, let's prioritize correctness of WW/WL.
                // We will use generateSliceBitmap.

                const { windowWidth, windowLevel, isAuto } = payload;
                bitmap = await generateSliceBitmap(niftiHeader, niftiImage, sliceIndex, windowWidth, windowLevel, isAuto);
            } else {
                // Fallback / Base only path
                const { windowWidth, windowLevel, isAuto } = payload;
                bitmap = await generateSliceBitmap(niftiHeader, niftiImage, sliceIndex, windowWidth, windowLevel, isAuto);
            }

            let maskBitmap = null;
            if (maskHeader && maskImage) {
                maskBitmap = await generateMaskBitmap(maskHeader, maskImage, sliceIndex);
            }

            const transferList = [bitmap];
            if (maskBitmap) transferList.push(maskBitmap);

            self.postMessage({
                type: 'SLICE_READY',
                payload: { sliceIndex, baseBitmap: bitmap, maskBitmap }
            }, transferList);

        } catch (err) {
            console.error(err);
            self.postMessage({ type: 'ERROR', payload: err.message });
        }
    }
};

const preCalculateMergedVolume = (header, image, maskHeader, maskImage) => {
    const dims = header.dims;
    const width = dims[1];
    const height = dims[2];
    const depth = dims[3];
    const totalSize = width * height * depth;

    // Base Data
    const baseData = getTypedData(header, image);

    // Mask Data
    const maskData = getTypedData(maskHeader, maskImage);

    // Result: Uint32Array (RGBA) for the whole volume
    const result = new Uint32Array(totalSize);

    // Normalize Base
    let min = Infinity;
    let max = -Infinity;
    // We can sample or just loop all. Looping all is safer.
    for (let i = 0; i < baseData.length; i++) {
        const val = baseData[i];
        if (val < min) min = val;
        if (val > max) max = val;
    }
    const range = max - min || 1;

    // Pre-calc colors
    // Mask: Red (255, 0, 0) alpha 0.4
    // We do the blending here once.

    for (let i = 0; i < totalSize; i++) {
        const baseVal = Math.floor(((baseData[i] - min) / range) * 255);

        if (maskData[i] > 0) {
            // Blend Red
            const r = Math.min(255, 102 + baseVal * 0.6); // 102 = 255 * 0.4
            const g = baseVal * 0.6;
            const b = baseVal * 0.6;
            result[i] = (255 << 24) | (b << 16) | (g << 8) | r;
        } else {
            // Base only
            result[i] = (255 << 24) | (baseVal << 16) | (baseVal << 8) | baseVal;
        }
    }

    return result;
};

const generateBitmapFromCache = async (volume, header, sliceIndex) => {
    const dims = header.dims;
    const width = dims[1];
    const height = dims[2];
    const sliceSize = width * height;
    const offset = sliceIndex * sliceSize;

    // Extract slice from pre-calculated volume
    const sliceBuffer = volume.subarray(offset, offset + sliceSize);

    // Create ImageData
    // Uint32Array view needs to be cast to Uint8ClampedArray for ImageData
    // But ImageData expects Uint8ClampedArray (RGBA order). 
    // Our Uint32Array is Little Endian (ABGR on x86).
    // (255 << 24) is Alpha.
    // If we just pass the buffer, it should work if we packed it correctly for the architecture.
    // Assuming Little Endian (standard for web):
    // 32-bit: A B G R (memory: R G B A)
    // So packing as (A << 24) | (B << 16) | (G << 8) | R is correct for R G B A in memory.

    const rgbaData = new Uint8ClampedArray(sliceBuffer.buffer, sliceBuffer.byteOffset, sliceBuffer.byteLength);
    const imageData = new ImageData(rgbaData, width, height);

    return createImageBitmap(imageData);
};

const getTypedData = (header, image) => {
    if (header.datatypeCode === 2) return new Uint8Array(image);
    if (header.datatypeCode === 4) return new Int16Array(image);
    if (header.datatypeCode === 16) return new Float32Array(image);
    return new Uint8Array(image);
};

const generateSliceBitmap = async (header, image, sliceIndex, windowWidth, windowLevel, isAuto) => {
    const dims = header.dims;
    const xDim = dims[1];
    const yDim = dims[2];
    const width = xDim;
    const height = yDim;
    const sliceSize = width * height;
    const offset = sliceIndex * sliceSize;

    // Create typed view
    const typedData = getTypedData(header, image);

    const sliceData = typedData.subarray(offset, offset + sliceSize);

    let min, max, range;

    if (isAuto) {
        // Normalize
        min = Infinity;
        max = -Infinity;
        for (let i = 0; i < sliceData.length; i++) {
            const val = sliceData[i];
            if (val < min) min = val;
            if (val > max) max = val;
        }
        range = max - min || 1;
    } else {
        // WW/WL Logic
        // lower = level - width / 2
        // upper = level + width / 2
        // val = (val - lower) / (upper - lower) * 255
        const widthVal = windowWidth || 1;
        const levelVal = windowLevel || 0;
        min = levelVal - (widthVal / 2);
        max = levelVal + (widthVal / 2);
        range = max - min || 1;
    }

    const rgbaData = new Uint8ClampedArray(width * height * 4);
    const buf32 = new Uint32Array(rgbaData.buffer);

    for (let i = 0; i < sliceData.length; i++) {
        let val = sliceData[i];

        // Apply Windowing
        if (val < min) val = min;
        else if (val > max) val = max;

        val = Math.floor(((val - min) / range) * 255);

        buf32[i] = (255 << 24) | (val << 16) | (val << 8) | val;
    }

    const imageData = new ImageData(rgbaData, width, height);
    return createImageBitmap(imageData);
};

const generateMaskBitmap = async (header, image, sliceIndex) => {
    const dims = header.dims;
    const xDim = dims[1];
    const yDim = dims[2];
    const width = xDim;
    const height = yDim;
    const sliceSize = width * height;
    const offset = sliceIndex * sliceSize;

    const typedData = getTypedData(header, image);

    const sliceData = typedData.subarray(offset, offset + sliceSize);

    const rgbaData = new Uint8ClampedArray(width * height * 4);
    const buf32 = new Uint32Array(rgbaData.buffer);
    const maskColor = (128 << 24) | (0 << 16) | (0 << 8) | 255; // Red, semi-transparent
    const transparent = 0;

    for (let i = 0; i < sliceData.length; i++) {
        buf32[i] = sliceData[i] > 0 ? maskColor : transparent;
    }

    const imageData = new ImageData(rgbaData, width, height);
    return createImageBitmap(imageData);
};
