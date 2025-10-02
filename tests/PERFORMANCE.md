# Performance Testing Guide

This directory contains comprehensive performance and pressure tests for Fastrict, demonstrating its high-performance characteristics under various load conditions.

## 🧪 Test Files

### `test_performance.py`
Comprehensive performance test suite including:
- **Single Request Latency**: Sub-millisecond response times
- **Sequential Performance**: Throughput under sequential load
- **Concurrent Performance**: High-load concurrent request handling
- **Rate Limiting Accuracy**: Precise rate limit enforcement under load
- **Extreme Load Testing**: System stability under pressure
- **Memory Efficiency**: Performance with thousands of unique keys
- **Sustained Load Endurance**: Long-running performance stability
- **Mode Comparison**: Global vs Per-Route performance comparison

### `demo_performance.py`
Live performance demonstration that:
- Starts a temporary FastAPI server
- Runs real HTTP requests through the rate limiter
- Demonstrates real-world performance characteristics
- Shows rate limiting headers and accuracy

## 🚀 Running the Tests

### Prerequisites

1. **Conda Environment**: Use the `chat` conda environment
2. **Dependencies**: Install required packages
3. **Fastrict**: Install in development mode

```bash
# Activate conda environment
conda activate chat

# Install dependencies
pip install pytest httpx pytest-asyncio uvicorn

# Install fastrict in development mode
pip install -e .
```

### Run Performance Tests

```bash
# Run comprehensive performance test suite
python -m pytest tests/test_performance.py -v

# Run tests with detailed output
python -m pytest tests/test_performance.py -v -s

# Run specific test category
python -m pytest tests/test_performance.py::TestPerformanceBenchmarks -v
python -m pytest tests/test_performance.py::TestPressureTests -v
```

### Run Performance Demo

```bash
# Run live performance demonstration
python test/demo_performance.py
```

### Generate Performance Report

```bash
# Run tests and generate README section
python test/run_performance_tests.py
```

## 📊 Latest Benchmark Results

*Environment: MacOS M1 Pro, Python 3.10.16, conda chat environment*

### Key Performance Metrics

| Metric | Value | Test Type |
|--------|-------|-----------|
| **Single Request Latency** | 0.37ms | Individual request |
| **Sequential Throughput** | 2,857 RPS | 1,000 sequential requests |
| **Concurrent Throughput** | 3,676 RPS | 50 users × 20 requests |
| **Extreme Load Throughput** | 3,639 RPS | 100 users × 10 requests |
| **Success Rate** | 100% | All load conditions |
| **Rate Limiting Accuracy** | 100% | Perfect enforcement |
| **P99 Response Time** | 32.56ms | 99th percentile under load |

### Performance Highlights

- ⚡ **Sub-millisecond latency** for single requests
- 🚀 **3,600+ RPS** sustained throughput
- 🎯 **100% success rate** under all conditions
- 🛡️ **Perfect rate limiting** accuracy
- 💾 **Memory efficient** with unique keys
- 🔄 **Stable performance** over time

## 🔬 Test Architecture

### Memory Backend
Tests use the in-memory storage backend for optimal performance testing:
- Eliminates network latency to Redis
- Shows pure rate limiting performance
- Provides consistent benchmark environment

### Async Testing
All tests use asyncio and httpx for:
- Realistic concurrent load simulation
- Non-blocking request handling
- High-performance test execution

### Load Patterns
Tests cover various real-world scenarios:
- Single user interactions
- Sequential API calls
- Burst concurrent traffic
- Sustained load over time
- Extreme pressure conditions

## 🎯 Test Scenarios

### 1. Single Request Latency
Measures the overhead of rate limiting on individual requests.

### 2. Sequential Performance
Tests throughput when requests come in sequentially (typical API usage).

### 3. Concurrent Performance
Simulates multiple users making requests simultaneously.

### 4. Rate Limiting Accuracy
Verifies that rate limits are enforced correctly under high load.

### 5. Extreme Load Test
Pushes the system to its limits with massive concurrent load.

### 6. Memory Efficiency
Tests performance with thousands of unique rate limiting keys.

### 7. Sustained Load Endurance
Long-running test to verify performance stability over time.

### 8. Mode Comparison
Compares Global vs Per-Route rate limiting performance.

## 📈 Performance Tuning

### For Maximum Performance
- Use in-memory backend for development/testing
- Use Redis with connection pooling for production
- Configure appropriate rate limiting strategies
- Monitor memory usage with many unique keys

### Production Considerations
- Redis cluster for horizontal scaling
- Connection pooling and timeout configuration
- Monitoring and alerting setup
- Regular performance testing in production-like environment

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors**: Ensure fastrict is installed in development mode
2. **Redis Connection**: Tests use memory backend, no Redis required
3. **Port Conflicts**: Demo uses port 8888, ensure it's available
4. **Slow Performance**: Check system resources and other running processes

### Expected Performance Ranges

| Environment | RPS Range | Latency Range |
|-------------|-----------|---------------|
| **MacOS M1** | 2,000-4,000 | 0.3-2.0ms |
| **Linux Server** | 3,000-6,000 | 0.2-1.5ms |
| **Cloud Instance** | 1,000-3,000 | 0.5-3.0ms |

*Performance varies based on hardware, system load, and configuration.*