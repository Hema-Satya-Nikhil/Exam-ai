import {
  lockPaperQuestion,
  regeneratePaperQuestion,
  unlockPaperQuestion,
} from '../lib/api';

const fetchMock = jest.fn();

beforeEach(() => {
  fetchMock.mockReset();
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

describe('paper review API payloads', () => {
  it('sends the Part A composite key for regeneration', async () => {
    fetchMock.mockReturnValueOnce(jsonOnce({ ok: true }));
    await regeneratePaperQuestion(
      'paper-1',
      { exam_part: 'short_answer', question_number: 5, group_number: null, part_label: null },
      'make it analytical',
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      exam_part: 'short_answer',
      question_number: 5,
      group_number: null,
      part_label: null,
      instructions: 'make it analytical',
    });
  });

  it('sends the Part B composite key for lock and unlock', async () => {
    fetchMock.mockReturnValueOnce(jsonOnce({ ok: true }));
    await lockPaperQuestion('paper-1', {
      exam_part: 'main',
      question_number: 51,
      group_number: 5,
      part_label: 'a',
    });
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      exam_part: 'main',
      question_number: 51,
      group_number: 5,
      part_label: 'a',
    });

    fetchMock.mockReturnValueOnce(jsonOnce({ ok: true }));
    await unlockPaperQuestion('paper-1', {
      exam_part: 'main',
      question_number: 51,
      group_number: 5,
      part_label: 'a',
    });
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      exam_part: 'main',
      question_number: 51,
      group_number: 5,
      part_label: 'a',
    });
  });
});
