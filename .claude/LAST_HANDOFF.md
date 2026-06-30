╭───────────────────────────── Session 上下文交接 ─────────────────────────────╮
│ 项目: /Users/ljn/Documents/demo/finished/ai-agent-learning                   │
│                                                                              │
│ Git 分支: main 时间: 2026-06-30 18:12                                        │
│                                                                              │
│ 用户需求记录                                                                 │
│                                                                              │
│  1 send-mail /send-mail 伊军 昨天和今天日报                                  │
│                                                                              │
│ 关键结论与分析                                                               │
│                                                                              │
│ [1] Base directory for this skill: /Users/ljn/.claude/skills/send-mail #     │
│ 邮件发送 Skill 通过 SMTP 协议发送邮件，自动处理附件。 ## 环境变量配置        │
│ 使用前需设置以下环境变量（在 ~/.zshrc 或 ~/.bashrc 中添加）： bash export    │
│ MAIL_SMTP_SERVER="smtp.qiye.163.com" export MAIL_SMTP_PORT="465" export      │
│ MAIL_USERNAME="junnan.liu_sx@aispeech.com" export MAIL_PASSWORD="你的授权码" │
│ ## 执行步骤 当用户要求发送邮件时： ### 1. 解析用户意图 从用户消息中提取： -  │
│ 收件人：用户指定的收件人邮箱，未指定则                                       │
│                                                                              │
│ [2] 伊军邮箱：yijun.zhu@aispeech.com。今天是 2026-06-30，昨天是              │
│ 2026-06-29。我去找对应日报文件。                                             │
│                                                                              │
│ [3] 邮件已发送成功。 - 收件人：伊军 yijun.zhu@aispeech.com - 主题：今日日报  │
│ - 附件：今日日报0629.docx、今日日报0630.docx                                 │
│                                                                              │
│ 关键命令                                                                     │
│                                                                              │
│  • date "+今天: %Y-%m-%d (%A)"; date -v-1d "+昨天: %Y-%m-%d (%A)"            │
│  • python3 /Users/ljn/.claude/skills/send-mail/scripts/send_email.py \ --to  │
│    yijun.zhu@aispeech.com \ --subject "今日日报" \ --body "" \ --attachments │
│    /Users/ljn/Desktop/aispeech/日报/今日日报0629.docx /Use                   │
│                                                                              │
│ ---------------------------------------------------------------------------- │
│                                                                              │
│ Session ce1d1cbb | 1 条需求                                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
