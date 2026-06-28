"""批量生成工单知识库主题内容（用 LLM 生成初稿，写入 data/knowledge_base/*.md）。

设计原则:
- 一次性脚本,直接调 OpenAI 兼容接口,不走项目的 CachedLLMClient(避免 trace/cache 干扰)
- 5 并发,跑完 90 个约 30-60 秒
- 已存在的文件默认跳过(防止覆盖手写内容),--force 可强制重写

用法:
    python scripts/gen_knowledge_bulk.py --dry-run         # 只打印主题清单
    python scripts/gen_knowledge_bulk.py --limit 3         # 只生成前 3 个(测试)
    python scripts/gen_knowledge_bulk.py                   # 生成全部 90 个
    python scripts/gen_knowledge_bulk.py --force           # 强制覆盖已存在文件
"""

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.multi_agent_system.config import Settings  # noqa: E402

KB_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge_base"

# ── 90 个新增主题(原有 10 个 md 保留,共 100 个) ──────────────────────────────
TOPICS: list[dict] = [
    # ── Technical 技术支持(13) ──
    {"slug": "tech-cache-redis", "category": "technical", "title": "Redis 缓存问题排查指南",
     "points": ["缓存穿透/击穿/雪崩的区别和处理", "热点 key 排查", "内存淘汰策略选择"]},
    {"slug": "tech-network-latency", "category": "technical", "title": "网络延迟诊断手册",
     "points": ["端到端延迟拆解(DNS/TCP/TLS/Server)", "MTR/tcpdump 用法", "CDN vs 回源对比"]},
    {"slug": "tech-cors", "category": "technical", "title": "跨域 CORS 错误处理",
     "points": ["预检请求 OPTIONS 流程", "常见 Origin/Headers 配置错误", "Cookie 跨域注意点"]},
    {"slug": "tech-cpu-spike", "category": "technical", "title": "CPU 飙升分析",
     "points": ["top/perf 火焰图定位", "死循环/正则回溯/频繁 GC", "限流降级方案"]},
    {"slug": "tech-memory-leak", "category": "technical", "title": "内存泄漏定位",
     "points": ["RSS 持续上涨监控", "pmap/objgraph 工具", "常见泄漏模式(闭包/缓存/连接)"]},
    {"slug": "tech-disk-full", "category": "technical", "title": "磁盘满处理",
     "points": ["大文件定位(ncdu/du)", "日志压缩策略", "inode 耗尽排查"]},
    {"slug": "tech-websocket", "category": "technical", "title": "WebSocket 断连排查",
     "points": ["心跳/Ping-Pong 配置", "代理/防火墙超时", "重连退避策略"]},
    {"slug": "tech-502-504", "category": "technical", "title": "502/504 网关错误排查",
     "points": ["Nginx upstream 配置", "后端响应超时", "健康检查与剔除"]},
    {"slug": "tech-cdn-failure", "category": "technical", "title": "CDN 故障处理",
     "points": ["CDN 节点不可达切换", "缓存命中率低排查", "回源策略调优"]},
    {"slug": "tech-ssl-cert", "category": "technical", "title": "SSL 证书过期处理",
     "points": ["证书到期监控告警", "Let's Encrypt 自动续期", "证书链不完整排查"]},
    {"slug": "tech-dns-issue", "category": "technical", "title": "DNS 解析问题",
     "points": ["dig/nslookup 用法", "TTL 与缓存", "本地 hosts 优先级"]},
    {"slug": "tech-oauth", "category": "technical", "title": "OAuth 授权失败排查",
     "points": ["redirect_uri 不匹配", "scope 不足", "state 防 CSRF"]},
    {"slug": "tech-captcha", "category": "technical", "title": "验证码异常处理",
     "points": ["短信/邮件验证码延迟", "图形验证码识别失败", "频控与黑名单"]},

    # ── Billing 账务(9) ──
    {"slug": "billing-invoice", "category": "billing", "title": "发票开具流程",
     "points": ["增值税普票/专票区别", "电子发票推送邮箱", "开票信息修改"]},
    {"slug": "billing-subscription-cancel", "category": "billing", "title": "订阅取消与降级",
     "points": ["立即取消 vs 周期末", "数据保留期 90 天", "已付费用不退"]},
    {"slug": "billing-double-charge", "category": "billing", "title": "重复扣费处理",
     "points": ["支付平台对账", "1 工作日内退款", "防止二次扣款"]},
    {"slug": "billing-refund-delay", "category": "billing", "title": "退款延迟排查",
     "points": ["银行处理时效 5-7 天", "退款流水号查询", "节假日顺延"]},
    {"slug": "billing-coupon", "category": "billing", "title": "优惠券使用规则",
     "points": ["有效期与适用范围", "叠加/互斥规则", "退款后退回"]},
    {"slug": "billing-tax", "category": "billing", "title": "企业开票税号管理",
     "points": ["三证合一税号校验", "专票资质审核", "开具时限 30 天"]},
    {"slug": "billing-foreign-currency", "category": "billing", "title": "外币支付处理",
     "points": ["汇率按支付平台", "USD/JPY/EUR 支持", "外汇申报阈值"]},
    {"slug": "billing-promotion", "category": "billing", "title": "促销活动规则",
     "points": ["满减/折扣/赠品", "活动叠加规则", "退款后活动撤销"]},
    {"slug": "billing-contract", "category": "billing", "title": "企业合同签订",
     "points": ["电子合同签章流程", "对公打款凭证", "框架协议 + 订单模式"]},

    # ── Complaint 投诉(10) ──
    {"slug": "complaint-escalation", "category": "complaint", "title": "投诉升级流程",
     "points": ["P0/P1 触发条件", "升级路径 客服→经理→总监", "响应时效 SLA"]},
    {"slug": "complaint-emotional", "category": "complaint", "title": "客户情绪安抚",
     "points": ["LAST 法则(倾听/道歉/解决/感谢)", "禁用话术清单", "升级转接时机"]},
    {"slug": "complaint-compensation", "category": "complaint", "title": "赔偿方案制定",
     "points": ["赔偿档位(全额/半额/赠品)", "审批权限分配", "二次确认防薅羊毛"]},
    {"slug": "complaint-mass", "category": "complaint", "title": "群体性投诉处理",
     "points": ["同源问题识别", "统一口径沟通", "专项小组对接"]},
    {"slug": "complaint-media", "category": "complaint", "title": "媒体曝光应对",
     "points": ["舆情监控告警", "公关团队介入", "对外声明模板"]},
    {"slug": "complaint-legal", "category": "complaint", "title": "法务介入场景",
     "points": ["律师函处理流程", "诉讼案件移交", "证据保全要求"]},
    {"slug": "complaint-repeat", "category": "complaint", "title": "重复投诉治理",
     "points": ["工单合并规则", "客户档案标签", "专项服务回访"]},
    {"slug": "complaint-survey", "category": "complaint", "title": "满意度回访",
     "points": ["NPS 评分口径", "回访话术模板", "差评客户 24h 二次回访"]},
    {"slug": "complaint-service-recovery", "category": "complaint", "title": "服务补救",
     "points": ["5 步补救法", "客户期望管理", "补救后跟踪"]},
    {"slug": "complaint-vip", "category": "complaint", "title": "VIP 投诉专项",
     "points": ["VIP 专属通道", "1h 响应承诺", "客户经理对接"]},

    # ── Inquiry 询盘(9) ──
    {"slug": "inquiry-onboarding", "category": "inquiry", "title": "新手引导",
     "points": ["注册到首次使用 5 步", "新用户引导浮层", "7 日激活漏斗"]},
    {"slug": "inquiry-pricing", "category": "inquiry", "title": "价格咨询",
     "points": ["分版定价对比", "阶梯用量计费", "年付优惠 8 折"]},
    {"slug": "inquiry-comparison", "category": "inquiry", "title": "版本对比",
     "points": ["免费版 vs 专业版 vs 企业版", "升级路径", "差异点 FAQ"]},
    {"slug": "inquiry-trial", "category": "inquiry", "title": "试用申请",
     "points": ["14 天专业版试用", "功能限制说明", "试用结束自动降级"]},
    {"slug": "inquiry-demo", "category": "inquiry", "title": "演示预约",
     "points": ["线上 demo 30 分钟", "行业解决方案", "售前顾问对接"]},
    {"slug": "inquiry-renewal", "category": "inquiry", "title": "续费提醒",
     "points": ["到期前 7/3/1 天提醒", "续费优惠", "断保后数据保留"]},
    {"slug": "inquiry-migration", "category": "inquiry", "title": "数据迁移",
     "points": ["Excel/CSV/API 三种导入", "迁移工具下载", "字段映射配置"]},
    {"slug": "inquiry-training", "category": "inquiry", "title": "培训服务",
     "points": ["线上视频课", "线下企业培训报价", "认证考试"]},
    {"slug": "inquiry-partner", "category": "inquiry", "title": "合作伙伴咨询",
     "points": ["分销/集成/服务商三类", "返点政策", "对接文档"]},

    # ── Security 安全(9) ──
    {"slug": "security-account-theft", "category": "security", "title": "账号盗用处理",
     "points": ["异常登录识别", "强制改密 + 设备下线", "证据保全与上报"]},
    {"slug": "security-phishing", "category": "security", "title": "钓鱼邮件识别",
     "points": ["伪造发件人检查", "可疑链接识别", "员工安全培训"]},
    {"slug": "security-data-breach", "category": "security", "title": "数据泄露应急",
     "points": ["应急响应 4 步", "监管上报 72h", "用户告知原则"]},
    {"slug": "security-2fa-lost", "category": "security", "title": "二次验证丢失",
     "points": ["备用码恢复", "人工身份核验", "重置后强制重绑"]},
    {"slug": "security-permission", "category": "security", "title": "权限申请",
     "points": ["最小权限原则", "审批流 工单→主管→IT", "定期权限复核"]},
    {"slug": "security-audit", "category": "security", "title": "安全审计",
     "points": ["ISO27001/SOC2 框架", "操作日志全量留存", "每季度内审"]},
    {"slug": "security-vulnerability", "category": "security", "title": "漏洞上报响应",
     "points": ["白帽提交渠道", "CVSS 评分定级", "修复 SLA 90 天"]},
    {"slug": "security-incident-response", "category": "security", "title": "安全事件响应",
     "points": ["事件分级 P0/P1/P2", "事件指挥官机制", "复盘 + 改进项跟踪"]},
    {"slug": "security-gdpr", "category": "security", "title": "GDPR 合规",
     "points": ["欧盟用户数据处理", "DSR 用户请求", "数据出境 SCC"]},

    # ── SLA/故障(9) ──
    {"slug": "sla-definition", "category": "sla", "title": "SLA 计算方法",
     "points": ["可用率 = (总分钟 - 不可用分钟) / 总分钟", "维护窗口不计", "月度结算"]},
    {"slug": "sla-compensation", "category": "sla", "title": "SLA 赔付申请",
     "points": ["不达标自动触发", "赔付比例 10%-50%", "次月账单抵扣"]},
    {"slug": "sla-status-page", "category": "sla", "title": "状态页使用",
     "points": ["status.example.com 实时更新", "邮件/短信订阅", "历史故障归档"]},
    {"slug": "sla-incident-report", "category": "sla", "title": "故障报告",
     "points": ["复盘报告模板", "5why 根因分析", "改进项 deadline"]},
    {"slug": "sla-maintenance-window", "category": "sla", "title": "维护窗口",
     "points": ["每周三 02:00-04:00", "7 天提前通知", "灰度发布 30 分钟"]},
    {"slug": "sla-degradation", "category": "sla", "title": "性能降级处理",
     "points": ["P99 延迟 > 3s 告警", "限流降级预案", "熔断配置"]},
    {"slug": "sla-dr", "category": "sla", "title": "灾难恢复",
     "points": ["RTO 4h / RPO 1h", "同城双活 + 异地冷备", "每季度演练"]},
    {"slug": "sla-monitoring", "category": "sla", "title": "监控告警",
     "points": ["4 金指标(延迟/流量/错误/饱和度)", "告警分级 pagerduty", "降噪策略"]},
    {"slug": "sla-communication", "category": "sla", "title": "故障沟通",
     "points": ["30 分钟更新一次", "客户群里同步进展", "对外话术模板"]},

    # ── Ops 运维(9) ──
    {"slug": "ops-deploy", "category": "ops", "title": "部署流程",
     "points": ["CI/CD 流水线 7 道门", "蓝绿/金丝雀发布", "发布单 + 审批"]},
    {"slug": "ops-rollback", "category": "ops", "title": "版本回滚",
     "points": ["15 分钟内错误率 > 1% 触发", "镜像版本切换", "DDL 不可回滚要前置"]},
    {"slug": "ops-scaling", "category": "ops", "title": "弹性扩容",
     "points": ["HPA CPU > 70% 扩容", "预热避免冷启动", "缩容冷却期 10 分钟"]},
    {"slug": "ops-log", "category": "ops", "title": "日志查询",
     "points": ["ELK + trace_id 串联", "保留 30 天热数据", "审计日志 180 天"]},
    {"slug": "ops-alerting", "category": "ops", "title": "告警处理",
     "points": ["PagerDuty值班轮转", "P0 5 分钟内 ack", "误报治理"]},
    {"slug": "ops-capacity", "category": "ops", "title": "容量规划",
     "points": ["QPS/存储/带宽预测", "双 11 / 618 压测", "容量水位 60% 报警"]},
    {"slug": "ops-db-migration", "category": "ops", "title": "数据库迁移",
     "points": ["gh-ost 在线 DDL", "停机窗口", "回滚预案 + 数据校验"]},
    {"slug": "ops-zerodowntime", "category": "ops", "title": "零停机发布",
     "points": ["优雅关闭信号处理", "健康检查就绪探针", "新旧版本兼容 2 周以上"]},
    {"slug": "ops-cost", "category": "ops", "title": "成本优化",
     "points": ["闲置资源识别", "Spot 实例 + 抢占式", "存储生命周期分层"]},

    # ── Integration 集成(9) ──
    {"slug": "integration-webhook-config", "category": "integration", "title": "Webhook 配置",
     "points": ["事件订阅筛选", "HMAC 签名校验", "失败重试 3/5/30 分钟"]},
    {"slug": "integration-sso", "category": "integration", "title": "SSO 单点登录",
     "points": ["SAML / OIDC 协议", "IdP 元数据配置", "JIT 自动开通账号"]},
    {"slug": "integration-api-key", "category": "integration", "title": "API Key 管理",
     "points": ["工作空间隔离", "权限作用域", "到期轮换策略"]},
    {"slug": "integration-oss", "category": "integration", "title": "对象存储接入",
     "points": ["S3 兼容协议", "STS 临时凭证", "CDN 加速 + 防盗链"]},
    {"slug": "integration-sms", "category": "integration", "title": "短信服务",
     "points": ["验证码 / 营销 / 通知三类", "签名报备", "回执率 99%"]},
    {"slug": "integration-email", "category": "integration", "title": "邮件服务",
     "points": ["事务性 vs 营销性", "SPF/DKIM/DMARC", "退订链接强制"]},
    {"slug": "integration-payment", "category": "integration", "title": "支付接口",
     "points": ["微信/支付宝/银联", "异步通知 + 主动查询双保险", "对账 T+1"]},
    {"slug": "integration-map", "category": "integration", "title": "地图服务",
     "points": ["高德/百度/腾讯选型", "POI 检索 / 路线规划", "配额限制"]},
    {"slug": "integration-ai", "category": "integration", "title": "AI 模型对接",
     "points": ["OpenAI 兼容协议", "Function Calling 工具", "Token 成本控制"]},

    # ── Mobile 移动(4) ──
    {"slug": "mobile-ios-crash", "category": "mobile", "title": "iOS 闪退排查",
     "points": ["crash log 符号化", "低内存kill 识别", "Bugly 集成"]},
    {"slug": "mobile-android-compat", "category": "mobile", "title": "Android 兼容性",
     "points": ["厂商 ROM 适配", "64位 so 库", "Android 高版本权限变化"]},
    {"slug": "mini-program", "category": "mobile", "title": "小程序常见问题",
     "points": ["授权/登录流程", "包体 2MB 限制 + 分包", "审核常见拒绝原因"]},
    {"slug": "mobile-offline", "category": "mobile", "title": "离线模式",
     "points": ["本地 SQLite 缓存", "断网队列上传", "冲突合并策略"]},

    # ── Release 发布(4) ──
    {"slug": "release-rollback", "category": "release", "title": "版本回滚流程",
     "points": ["发布即默认带回滚脚本", "DDL 不可逆要前置灰度", "回滚决策权限"]},
    {"slug": "release-breaking", "category": "release", "title": "不兼容变更",
     "points": ["API 版本 v1/v2 并存 12 月", "迁移文档 + 工具", "提前 90 天通知"]},
    {"slug": "release-beta", "category": "release", "title": "Beta 测试",
     "points": ["TestFlight / 内测渠道", "灰度 1%/10%/50%", "反馈收集表单"]},
    {"slug": "release-hotfix", "category": "release", "title": "紧急修复",
     "points": ["hotfix 走快通道", "事后补回归测试", "复盘 + 流程改进"]},

    # ── 凑数的额外主题(5) ──
    {"slug": "tech-rate-limit", "category": "technical", "title": "限流策略",
     "points": ["令牌桶 vs 滑动窗口", "Redis + Lua 原子计数", "429 Retry-After"]},
    {"slug": "tech-webhook-failure", "category": "technical", "title": "Webhook 失败排查",
     "points": ["5xx 重试,4xx 不重试", "死信队列", "失败告警 + 仪表盘"]},
    {"slug": "tech-timezone", "category": "technical", "title": "时区问题",
     "points": ["服务端 UTC 存储", "前端按浏览器时区显示", "DST 夏令时陷阱"]},
    {"slug": "inquiry-faq-account", "category": "inquiry", "title": "账号常见问题 FAQ",
     "points": ["注册/登录/改密", "账号合并", "注销数据清理"]},
    {"slug": "inquiry-faq-data", "category": "inquiry", "title": "数据导出 FAQ",
     "points": ["Excel/CSV/PDF 格式", "字段说明下载", "敏感字段脱敏"]},
]

assert len(TOPICS) == 90, f"主题数应为 90,实际 {len(TOPICS)}"

PROMPT_TEMPLATE = """你是技术支持知识库写手。请按以下信息生成一篇工单知识库文档。

标题: {title}
分类: {category}
覆盖要点: {points}

写作要求:
- Markdown 格式,第一行是 "# {title}"
- 总字数 600-900 字
- 结构包含: 适用场景 / 常见原因 / 排查步骤 / 解决方案 / 注意事项
- 用编号列表,不要废话和华丽修辞
- 实操性强,涉及命令或路径用 `代码` 包裹
- 不要使用 emoji
"""


def gen_one(client: OpenAI, model: str, topic: dict) -> str:
    """调 LLM 生成单个主题内容。"""
    prompt = PROMPT_TEMPLATE.format(
        title=topic["title"],
        category=topic["category"],
        points=" / ".join(topic["points"]),
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
    )
    return resp.choices[0].message.content.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="批量生成知识库主题")
    parser.add_argument("--dry-run", action="store_true", help="只打印主题清单")
    parser.add_argument("--limit", type=int, default=0, help="只生成前 N 个(测试用)")
    parser.add_argument("--force", action="store_true", help="已存在也覆盖")
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    if args.dry_run:
        print(f"共 {len(TOPICS)} 个主题:")
        for i, t in enumerate(TOPICS, 1):
            print(f"  {i:2d}. [{t['category']:12s}] {t['slug']:30s} | {t['title']}")
        return

    settings = Settings()
    client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key)
    KB_DIR.mkdir(parents=True, exist_ok=True)

    topics = TOPICS[: args.limit] if args.limit else TOPICS
    todo = [t for t in topics if args.force or not (KB_DIR / f"{t['slug']}.md").exists()]
    skipped = len(topics) - len(todo)
    print(f"总 {len(topics)} 个,跳过已存在 {skipped} 个,实际生成 {len(todo)} 个")
    print(f"LLM: {settings.llm_model} @ {settings.llm_base_url}")
    print(f"输出目录: {KB_DIR}\n")

    if not todo:
        print("无待生成,退出")
        return

    failed: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = {ex.submit(gen_one, client, settings.llm_model, t): t for t in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            t = futures[fut]
            try:
                content = fut.result()
                path = KB_DIR / f"{t['slug']}.md"
                path.write_text(content, encoding="utf-8")
                print(f"  [{i}/{len(todo)}] OK  {t['slug']}")
            except Exception as e:
                print(f"  [{i}/{len(todo)}] FAIL {t['slug']}: {type(e).__name__}: {str(e)[:80]}")
                failed.append((t["slug"], str(e)))

    print(f"\n完成: 成功 {len(todo) - len(failed)}, 失败 {len(failed)}")
    if failed:
        print("失败列表:")
        for slug, err in failed:
            print(f"  - {slug}: {err[:120]}")


if __name__ == "__main__":
    main()
