import { API_BASE_URL, AUTH_TOKEN_KEY } from '../utils/constants';

/**
 * Reusable HTTP API client wrapping Fetch API
 */
class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl.replace(/\/+$/, ''); // Remove trailing slashes
  }

  /**
   * Helper to retrieve auth token
   */
  getToken() {
    return localStorage.getItem(AUTH_TOKEN_KEY);
  }

  /**
   * Perform an HTTP request
   * @param {string} endpoint 
   * @param {Object} options 
   * @returns {Promise<any>}
   */
  async request(endpoint, { method = 'GET', body = null, headers = {}, ...customConfig } = {}) {
    const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    const url = `${this.baseUrl}${cleanEndpoint}`;

    const requestHeaders = {
      'Content-Type': 'application/json',
      ...headers
    };

    const token = this.getToken();
    if (token) {
      requestHeaders['Authorization'] = `Bearer ${token}`;
    }

    const config = {
      method,
      headers: requestHeaders,
      ...customConfig
    };

    if (body) {
      config.body = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(url, config);
    } catch (networkError) {
      const err = new Error(
        'Unable to connect to the server. Please check your internet connection or verify the backend is running.'
      );
      err.isNetworkError = true;
      throw err;
    }

    // Try to parse JSON response
    let data;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      try {
        data = await response.json();
      } catch {
        data = null;
      }
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      const message =
        (data && typeof data === 'object' && (data.message || data.error)) ||
        `Request failed with status ${response.status}`;

      const error = new Error(message);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  }

  /**
   * GET request
   */
  get(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'GET' });
  }

  /**
   * POST request
   */
  post(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'POST', body });
  }

  /**
   * PATCH request
   */
  patch(endpoint, body, options = {}) {
    return this.request(endpoint, { ...options, method: 'PATCH', body });
  }

  /**
   * DELETE request
   */
  delete(endpoint, options = {}) {
    return this.request(endpoint, { ...options, method: 'DELETE' });
  }

  // AI Conversation History Methods
  createConversation(title = null) {
    return this.post('/ai/conversations', { title });
  }

  getConversations(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.get(`/ai/conversations${query ? `?${query}` : ''}`);
  }

  getConversation(id) {
    return this.get(`/ai/conversations/${id}`);
  }

  deleteConversation(id) {
    return this.delete(`/ai/conversations/${id}`);
  }

  sendChatMessage(message, conversationId = null) {
    const payload = { message };
    if (conversationId) {
      payload.conversationId = conversationId;
    }
    return this.post('/ai/chat', payload);
  }

  // Productivity Tasks Methods
  getTasks(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.get(`/tasks${query ? `?${query}` : ''}`);
  }

  getTask(id) {
    return this.get(`/tasks/${id}`);
  }

  createTask(taskData) {
    return this.post('/tasks', taskData);
  }

  updateTask(id, taskData) {
    return this.patch(`/tasks/${id}`, taskData);
  }

  completeTask(id) {
    return this.patch(`/tasks/${id}/complete`);
  }

  incompleteTask(id) {
    return this.patch(`/tasks/${id}/incomplete`);
  }

  deleteTask(id) {
    return this.delete(`/tasks/${id}`);
  }
}

export const api = new ApiClient(API_BASE_URL);
export default api;


