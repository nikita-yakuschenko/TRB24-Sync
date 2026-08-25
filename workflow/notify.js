// YouTrack workflow sync-connector / notify.
// Секрет подставляется при загрузке, в git не класть.
const entities = require('@jetbrains/youtrack-scripting-api/entities');
const http = require('@jetbrains/youtrack-scripting-api/http');

const SKIP = {SYNC: true};
const HOST = 'https://sync-trb24-sync-79a0ac-155-212-147-165.sslip.io';
const SECRET = '{{WEBHOOK_SECRET}}';

exports.rule = entities.Issue.onChange({
  title: 'Notify TRB24-Sync',
  guard: function(ctx) {
    return !SKIP[ctx.issue.project.shortName];
  },
  // postAsync без 4-го аргумента уходит в той же транзакции: 404 коннектора откатывает issue.
  action: function(ctx) {
    var issue = ctx.issue;
    var connection = new http.Connection(HOST, null, 15000);
    connection.addHeader('Content-Type', 'application/json');
    connection.postAsync(
      '/hooks/youtrack?secret=' + SECRET,
      null,
      {id: issue.id, issueId: issue.idReadable},
      'onSyncResponse'
    );
  },
  asyncFunctions: {
    onSyncResponse: function(ctx) {
      if (ctx.response && !ctx.response.isSuccess) {
        console.warn('TRB24-Sync HTTP failed');
      }
    }
  }
});
