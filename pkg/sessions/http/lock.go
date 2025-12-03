package http

import (
	"context"
	"time"
)

// noOpLock is a no-op implementation of the Lock interface
// Distributed locking over HTTP is complex and may not be required for all use cases
type noOpLock struct{}

func newNoOpLock() *noOpLock {
	return &noOpLock{}
}

func (l *noOpLock) Obtain(ctx context.Context, expiration time.Duration) error {
	return nil
}

func (l *noOpLock) Peek(ctx context.Context) (bool, error) {
	return false, nil
}

func (l *noOpLock) Refresh(ctx context.Context, expiration time.Duration) error {
	return nil
}

func (l *noOpLock) Release(ctx context.Context) error {
	return nil
}
