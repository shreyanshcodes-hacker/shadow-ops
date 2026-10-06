'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Mail, AlertCircle, Loader2, CheckCircle, Shield, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Alert } from '@/components/ui/Alert';
import { getAuthInstance, getAuthErrorMessage } from '@/lib/auth';
import { sendEmailVerification, User } from 'firebase/auth';

export default function VerifyEmailPage() {
  const router = useRouter();
  const auth = getAuthInstance();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [verified, setVerified] = useState(false);

  const checkVerificationStatus = useCallback(async () => {
    const currentUser = auth.currentUser;
    if (currentUser) {
      await currentUser.reload();
      setUser(currentUser);
      if (currentUser.emailVerified) {
        setVerified(true);
        router.push('/dashboard');
        router.refresh();
      }
    }
    setLoading(false);
  }, [auth, router]);

  useEffect(() => {
    checkVerificationStatus();
  }, [checkVerificationStatus]);

  const handleResend = async () => {
    const currentUser = auth.currentUser;
    if (!currentUser) return;

    setSending(true);
    setError('');

    try {
      await sendEmailVerification(currentUser);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 5000);
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setSending(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    await checkVerificationStatus();
  };

  const handleLogout = async () => {
    await auth.signOut();
    router.push('/auth/login');
    router.refresh();
  };

  if (verified) {
    return null;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background-DEFAULT px-4 py-12">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4 p-2 rounded-lg bg-accent-glow">
            <Shield className="h-8 w-8 text-accent-DEFAULT" />
          </div>
          <CardTitle className="text-2xl font-bold">Verify Your Email</CardTitle>
          <CardDescription className="mt-2">
            We&apos;ve sent a verification email to <strong>{user?.email}</strong>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <span>{error}</span>
            </Alert>
          )}

          {success && (
            <Alert variant="success">
              <CheckCircle className="h-4 w-4" />
              <span>Verification email sent! Check your inbox.</span>
            </Alert>
          )}

          <Alert variant="info" className="bg-background-tertiary/50 border-border-DEFAULT">
            <Mail className="h-4 w-4" />
            <div className="text-sm">
              <p className="font-medium">Check your inbox (and spam folder)</p>
              <p className="text-foreground-muted mt-1">
                Click the verification link in the email, then click "I&apos;ve Verified" below.
              </p>
            </div>
          </Alert>

          <div className="flex gap-3">
            <Button
              onClick={handleRefresh}
              disabled={loading}
              className="flex-1"
              size="lg"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              I&apos;ve Verified
            </Button>
            <Button
              variant="outline"
              onClick={handleResend}
              disabled={sending || loading}
              className="flex-1"
              size="lg"
            >
              <Loader2 className={`h-4 w-4 mr-2 ${sending ? 'animate-spin' : ''}`} />
              Resend Email
            </Button>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border-DEFAULT" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background-DEFAULT px-2 text-foreground-muted">Or</span>
            </div>
          </div>

          <Button variant="ghost" onClick={handleLogout} className="w-full">
            <AlertCircle className="h-4 w-4 mr-2" />
            Sign Out & Use Different Account
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}