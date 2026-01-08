import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 300000, // 5 minutes
});

export const createJob = async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post('/api/v1/jobs', formData, {
        headers: {
            'Content-Type': 'multipart/form-data',
        },
    });
    return response.data;
};

export const triggerSegmentation = async (jobId, sliceIndex, bbox, windowLevel = null) => {
    const payload = {
        slice_index: sliceIndex,
        bounding_box: bbox,
    };

    if (windowLevel) {
        payload.window_level = windowLevel;
    }

    const response = await api.post(`/api/v1/jobs/${jobId}/initial-mask`, payload);
    return response.data;
};

export const getJobStatus = async (jobId) => {
    const response = await api.get(`/api/v1/jobs/${jobId}/status`);
    return response.data;
};

export const getJobResult = async (jobId) => {
    const response = await api.get(`/api/v1/jobs/${jobId}/result`);
    return response.data;
};

export const triggerPropagation = async (jobId, startSlice, endSlice, referenceSlice, maskData, windowLevel = null) => {
    const payload = {
        start_slice: startSlice,
        end_slice: endSlice,
        reference_slice: referenceSlice,
        mask_data: maskData,
    };

    if (windowLevel) {
        payload.window_level = windowLevel;
    }

    const response = await api.post(`/api/v1/jobs/${jobId}/propagate`, payload);
    return response.data;
};
export const getJobResultBlob = async (jobId) => {
    try {
        const response = await axios.get(`${API_BASE}/api/v1/jobs/${jobId}/result`, {
            responseType: 'arraybuffer'
        });
        return response.data;
    } catch (error) {
        console.error("Error fetching job result blob:", error);
        throw error;
    }
};
