import { apiFetch, getGenerationJob, queueGenerationJob, resumeGenerationJob } from '../lib/api';
import { logoutRequest } from '../lib/api';

const fetchMock = jest.fn();

beforeEach(() => {
  fetchMock.mockReset();
  // jsdom localStorage tokens for the auth header path
  window.localStorage.setItem('ecai_access_token', 'tok');
  window.localStorage.setItem('ecai_refresh_token', 'rtok');
  global.fetch = fetchMock as unknown as typeof global.fetch;
});

function jsonOnce(payload: unknown, status = 200) {
  return Promise.resolve({
    ok: status < 400,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    text: () => Promise.resolve(JSON.stringify(payload)),
    json: () => Promise.resolve(payload)
  } as Response);
}

function responseOnce(payload: unknown, status: number) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'content-type': 'application/json' }),
    text: () => Promise.resolve(JSON.stringify(payload)),
    json: () => Promise.resolve(payload)
  } as Response);
}

describe('async generation job API', () => {
  it('accepts a successful 204 logout without parsing JSON', async () => {
    fetchMock.mockReturnValueOnce(Promise.resolve({
      ok: true,
      status: 204,
      headers: new Headers(),
      json: jest.fn(() => Promise.reject(new Error('204 must not be parsed')))
    } as unknown as Response));

    await expect(logoutRequest('refresh-token')).resolves.toBeUndefined();
  });

  it('queues a job against /api/generation/jobs with the blueprint', async () => {
    fetchMock.mockReturnValueOnce(jsonOnce({ id: 'j1', status: 'queued' }));
    const job = await queueGenerationJob({ exam_type: 'MID 1' });
    expect(job.id).toBe('j1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/generation/jobs');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ blueprint: { exam_type: 'MID 1' } });
  });

  it('polls job status by id', async () => {
    fetchMock.mockReturnValueOnce(jsonOnce({
      id: 'j1', status: 'running', completed_questions: 2, total_questions: 11
    }));
    const job = await getGenerationJob('j1');
    expect(fetchMock.mock.calls[0][0]).toContain('/api/generation/jobs/j1');
    expect(job.completed_questions).toBe(2);
  });

  it('resumes a failed job via POST', async () => {
    fetchMock.mockReturnValueOnce(jsonOnce({ id: 'j1', status: 'queued' }));
    await resumeGenerationJob('j1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toContain('/api/generation/jobs/j1/resume');
    expect(init.method).toBe('POST');
  });

  it('refreshes once after a 401 and retries with the rotated access token', async () => {
    fetchMock
      .mockReturnValueOnce(responseOnce({}, 401))
      .mockReturnValueOnce(responseOnce({
        access_token: 'access-2',
        refresh_token: 'refresh-2',
        token_type: 'bearer'
      }, 200))
      .mockReturnValueOnce(jsonOnce({ ok: true }));

    await expect(apiFetch<{ ok: boolean }>('/api/protected')).resolves.toEqual({ ok: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[2][1].headers.Authorization).toBe('Bearer access-2');
    expect(window.localStorage.getItem('ecai_access_token')).toBe('access-2');
    expect(window.localStorage.getItem('ecai_refresh_token')).toBe('refresh-2');
  });

  it('shares one refresh request across concurrent 401 responses', async () => {
    let resolveRefresh!: (value: Response) => void;
    const refreshResponse = new Promise<Response>((resolve) => {
      resolveRefresh = resolve;
    });
    fetchMock
      .mockReturnValueOnce(responseOnce({}, 401))
      .mockReturnValueOnce(responseOnce({}, 401))
      .mockReturnValueOnce(refreshResponse)
      .mockReturnValueOnce(jsonOnce({ first: true }))
      .mockReturnValueOnce(jsonOnce({ second: true }));

    const first = apiFetch<{ first: boolean }>('/api/first');
    const second = apiFetch<{ second: boolean }>('/api/second');
    await Promise.resolve();
    resolveRefresh(await responseOnce({
      access_token: 'access-concurrent',
      refresh_token: 'refresh-concurrent',
      token_type: 'bearer'
    }, 200));

    await expect(first).resolves.toEqual({ first: true });
    await expect(second).resolves.toEqual({ second: true });
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });

  it('clears tokens and does not retry when refresh fails', async () => {
    fetchMock
      .mockReturnValueOnce(responseOnce({}, 401))
      .mockReturnValueOnce(responseOnce({}, 401));

    await expect(apiFetch('/api/protected')).rejects.toMatchObject({ status: 401 });
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(window.localStorage.getItem('ecai_access_token')).toBeNull();
    expect(window.localStorage.getItem('ecai_refresh_token')).toBeNull();
  });
});
