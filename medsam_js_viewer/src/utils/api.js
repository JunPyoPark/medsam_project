import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000'; // Adjust if needed or use env var

const api = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
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

export const triggerSegmentation = async (jobId, sliceIndex, bbox) => {
    const response = await api.post(`/api/v1/jobs/${jobId}/initial-mask`, {
        slice_index: sliceIndex,
        bounding_box: bbox,
    });
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

export const triggerPropagation = async (jobId, startSlice, endSlice, referenceSlice, maskData) => {
    const response = await api.post(`/api/v1/jobs/${jobId}/propagate`, {
        start_slice: startSlice,
        end_slice: endSlice,
        reference_slice: referenceSlice,
        mask_data: maskData,
    });
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
