/* Local regression for split RX-ring rollover with mergeable buffers. */
static void canary_wait_used(QVirtioDevice *dev, QVirtQueue *vq,
                             uint16_t expected, bool expect_stall)
{
    int64_t end = g_get_monotonic_time() + (expect_stall ? 300000 : 3000000);
    uint16_t used;
    do {
        used = qtest_readw(global_qtest, vq->used + 2);
        if (used == expected) {
            break;
        }
        g_usleep(1000);
    } while (g_get_monotonic_time() < end);
    if (expect_stall) {
        g_assert_cmpuint(used, !=, expected);
    } else {
        g_assert_cmpuint(used, ==, expected);
    }
}

static void canary_send_frames(int fd, const char *packet, size_t len,
                               unsigned count)
{
    size_t size = (len + 4) * count;
    char *batch = g_malloc(size);
    uint32_t netlen = htonl(len);
    for (unsigned i = 0; i < count; i++) {
        memcpy(batch + i * (len + 4), &netlen, 4);
        memcpy(batch + i * (len + 4) + 4, packet, len);
    }
    size_t done = 0;
    while (done < size) {
        ssize_t n = send(fd, batch + done, size - done, 0);
        g_assert_cmpint(n, >, 0);
        done += n;
    }
    g_free(batch);
}

static void rx_jumbo_wrap_test(void *obj, void *data, QGuestAllocator *alloc)
{
    QVirtioNet *net = obj;
    QVirtioDevice *dev = net->vdev;
    QVirtQueue *vq = net->queues[0];
    QTestState *qts = global_qtest;
    int fd = ((int *)data)[0];
    uint64_t bufs = guest_alloc(alloc, 256 * 2060);
    uint32_t consumed = 0;
    unsigned tail = getenv("CANARY_WRAP_TAIL") ? atoi(getenv("CANARY_WRAP_TAIL")) : 3;
    unsigned rounds = getenv("CANARY_ROUNDS") ? atoi(getenv("CANARY_ROUNDS")) : 3;
    bool expect_stall = getenv("CANARY_EXPECT_STALL") != NULL;
    char small[64] = {0};
    char jumbo[9229];
    memset(small, 0xff, 6);
    memset(jumbo, 0x5a, sizeof(jumbo));
    memset(jumbo, 0xff, 6);
    jumbo[6] = small[6] = 0x02;
    g_assert_cmpuint(vq->size, ==, 256);
    g_assert_cmpuint(tail, >=, 1);
    g_assert_cmpuint(tail, <=, 3);
    g_assert_cmpuint(rounds, <=, 10);
    for (unsigned i = 0; i < 256; i++) {
        qvirtqueue_add(qts, vq, bufs + 2060 * i, 2060, true, false);
        qtest_writew(qts, vq->avail + 4 + 2 * i, i);
    }
    for (unsigned round = 1; round <= rounds; round++) {
        uint32_t target = round * 65536 - tail;
        while (consumed < target) {
            unsigned n = MIN(256, target - consumed);
            qtest_writew(qts, vq->avail + 2, consumed + n);
            dev->bus->virtqueue_kick(dev, vq);
            canary_send_frames(fd, small, sizeof(small), n);
            consumed += n;
            canary_wait_used(dev, vq, consumed, false);
        }
        /* Advertise too few buffers across wrap and queue one jumbo frame. */
        qtest_writew(qts, vq->avail + 2, round * 65536 + (tail < 3 ? 1 : 0));
        dev->bus->virtqueue_kick(dev, vq);
        canary_send_frames(fd, jumbo, sizeof(jumbo), 1);
        g_usleep(100000);
        g_assert_cmpuint(qtest_readw(qts, vq->used + 2), ==,
                         (uint16_t)consumed);
        /* Replenish to a full ring and explicitly kick, as a guest would. */
        qtest_writew(qts, vq->avail + 2, consumed + 256);
        dev->bus->virtqueue_kick(dev, vq);
        canary_wait_used(dev, vq, consumed + 5, expect_stall);
        if (expect_stall) {
            g_assert_cmpuint(qtest_readw(qts, vq->used + 2), ==, (uint16_t)consumed);
            g_test_message("Confirmed RX stall at used=%u with 256 available buffers",
                           (uint16_t)consumed);
            break;
        }
        uint16_t merged = qtest_readw(qts,
                                       bufs + (consumed % 256) * 2060 + 10);
        g_assert_cmpuint(merged, ==, 5);
        size_t done = 0;
        for (unsigned i = 0; i < 5; i++) {
            unsigned skip = i ? 0 : VNET_HDR_SIZE;
            unsigned n = MIN(2060 - skip, sizeof(jumbo) - done);
            char received[2060];
            qtest_memread(qts, bufs + ((consumed + i) % 256) * 2060 + skip,
                          received, n);
            g_assert_cmpmem(received, n, jumbo + done, n);
            done += n;
        }
        consumed += 5;
        g_test_message("Jumbo delivered intact across wrap %u; used=%u",
                       round, (uint16_t)consumed);
    }
    guest_free(alloc, bufs);
}

