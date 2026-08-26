module.exports = {
  testEnvironment: 'jsdom',
  testEnvironmentOptions: {
    url: 'http://localhost:3000'
  },
  collectCoverage: true,
  coverageDirectory: '<rootDir>/coverage',
  coverageReporters: ['json', 'text', 'lcov', 'clover'],
  moduleFileExtensions: ['js', '.jsx', '.ts', '.tsx', '.json'],
  moduleName: 'ExamCraftAI',
  roots: ['<rootDir>/app/tests'],
  setupFiles: ['<rootDir>/app/setupTests.js'],
  testMatch: [
    '**/app/tests/**/*.{js,.jsx,.ts,.tsx}'
  ],
  transform: {
    '^.+\\.(js|jsx|ts|tsx)$': 'babel-jest'
  }
};