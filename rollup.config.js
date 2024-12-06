module.exports = [
  {
    input: 'src/javascripts/application.js',
    output: {
      file: 'application/static/javascripts/application.js',
      format: 'iife'
    }
  },
  {
    input: 'src/javascripts/table.js',
    output: {
      file: 'application/static/javascripts/table.js',
      format: 'iife'
    }
  },
  {
    input: 'src/javascripts/timetable.js',
    output: {
      file: 'application/static/javascripts/timetable.js',
      format: 'iife'
    }
  }
]
