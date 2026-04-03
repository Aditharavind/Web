module.exports = {
  ci: {
    collect: {
      startServerCommand: 'uvicorn app.main:app --host 0.0.0.0 --port 8000',
      url: [ 'http://127.0.0.1:8000/' ],
      numberOfRuns: 3
    },
    assert: {
      assertions: {
        'categories:performance': ['error', {minScore: 0.9}],
        'categories:accessibility': ['warn', {minScore: 0.9}]
      }
    },
    upload: {
      target: 'temporary-public-storage'
    }
  }
}
