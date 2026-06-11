#!/bin/bash
# Docker 一键部署脚本（在 HomeUbuntu 上执行）
# 用法: cd ~/ai-agent-learning && bash scripts/deploy-docker.sh

set -e

echo "=== Docker 部署 ai-agent-learning ==="

# 1. 清理旧容器
echo "停止旧容器..."
sudo docker stop ai-agent-learning_api_1 ai-agent-learning_qdrant_1 2>/dev/null || true
sudo docker rm ai-agent-learning_api_1 ai-agent-learning_qdrant_1 2>/dev/null || true

# 2. 确保代码目录存在
if [ ! -f "docker-compose.yml" ]; then
    echo "错误: 当前目录缺少 docker-compose.yml，请在项目根目录执行"
    exit 1
fi

# 3. 创建 .env（如果缺失）
if [ ! -f ".env" ]; then
    echo "创建 .env 文件..."
    cat > .env << 'EOF'
LLM_BASE_URL=http://172.16.58.68:11434
LLM_API_KEY=ollama
EMBEDDING_BASE_URL=http://172.16.58.68:11434
QDRANT_URL=http://qdrant:6333
CACHE_ENABLED=true
CACHE_MAX_SIZE=512
CACHE_TTL=300
EOF
fi

# 4. 构建并启动
echo "构建 API 镜像（使用清华镜像源）..."
sudo docker-compose build --no-cache api

echo "启动容器..."
sudo docker-compose up -d

# 5. 等待启动并验证
echo "等待 API 启动..."
sleep 5

for i in {1..10}; do
    HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo "")
    if echo "$HEALTH" | grep -q "healthy"; then
        echo ""
        echo "=== 部署成功 ==="
        echo "API 地址: http://172.16.58.68:8000"
        echo "健康检查: http://172.16.58.68:8000/health"
        echo "指标监控: http://172.16.58.68:8000/metrics"
        echo ""
        sudo docker-compose ps
        exit 0
    fi
    echo -n "."
    sleep 2
done

echo ""
echo "部署可能有问题，查看日志:"
sudo docker logs ai-agent-learning_api_1 --tail 30
