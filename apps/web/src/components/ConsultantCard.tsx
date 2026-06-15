import { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

function Toast({ name, phone, onDone }: { name: string; phone: string; onDone: () => void }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // trigger enter animation
    const t1 = setTimeout(() => setVisible(true), 10);
    // start exit animation after 3.5s
    const t2 = setTimeout(() => setVisible(false), 3500);
    // remove after exit animation
    const t3 = setTimeout(() => onDone(), 4200);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [onDone]);

  return createPortal(
    <div
      className={`fixed top-5 right-5 z-[9999] flex items-start gap-3 px-4 py-3.5 rounded-2xl shadow-2xl
                  bg-white border border-green-200 max-w-sm w-[calc(100vw-40px)]
                  transition-all duration-500
                  ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 -translate-y-3'}`}
    >
      {/* Icon */}
      <div className="shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-lg"
           style={{ backgroundColor: '#e6f9e8' }}>
        ✅
      </div>
      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-gray-900">Đăng ký thành công!</p>
        <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">
          Chuyên viên L&C sẽ liên hệ <strong className="text-gray-700">{name}</strong> qua{' '}
          <strong className="text-gray-700">{phone}</strong> trong vòng <strong className="text-gray-700">24 giờ</strong>.
        </p>
      </div>
      {/* Close */}
      <button onClick={() => { setVisible(false); setTimeout(onDone, 500); }}
              className="shrink-0 text-gray-300 hover:text-gray-500 transition-colors text-lg leading-none mt-0.5">
        ×
      </button>
      {/* Progress bar */}
      <div className="absolute bottom-0 left-0 right-0 h-0.5 rounded-b-2xl overflow-hidden">
        <div className="h-full animate-shrink" style={{ backgroundColor: '#2D9E34' }} />
      </div>
    </div>,
    document.body,
  );
}

interface Props {
  profileSummary: string;
  sessionId: string;
  startAtForm?: boolean;
  onContinueChat: () => void;
}

type State = 'ask' | 'form' | 'done';

export function ConsultantCard({ profileSummary, sessionId, startAtForm = false, onContinueChat }: Props) {
  const [state, setState] = useState<State>(startAtForm ? 'form' : 'ask');
  const [name, setName]   = useState('');
  const [phone, setPhone] = useState('');
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(false);

  const handleSubmit = async () => {
    if (!name.trim() || !phone.trim()) return;
    setLoading(true);
    try {
      await fetch(`${API_URL}/intake`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, phone, profile: profileSummary, session_id: sessionId }),
      });
      setToast(true);
      setState('done');
    } finally {
      setLoading(false);
    }
  };

  if (state === 'done') {
    return (
      <>
        {toast && <Toast name={name} phone={phone} onDone={() => setToast(false)} />}
        <div className="mt-3 rounded-xl border border-green-200 bg-green-50 dark:bg-green-900/20 p-4 text-center space-y-1">
          <div className="text-2xl">✅</div>
          <p className="text-sm font-semibold text-green-700 dark:text-green-300">Đã ghi nhận thông tin!</p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Chuyên viên L&C sẽ liên hệ <strong>{name}</strong> qua SĐT <strong>{phone}</strong> trong vòng <strong>24 giờ</strong>.
          </p>
          <p className="text-[10px] text-gray-400 pt-1">Hotline: 0903 857 257 · hai.tran@lncglobal.vn</p>
        </div>
      </>
    );
  }

  if (state === 'form') {
    return (
      <div className="mt-3 rounded-xl border border-[#0C3656] bg-blue-50/30 dark:bg-blue-900/10 p-4 space-y-3">
        <p className="text-sm font-semibold text-[#0C3656] dark:text-blue-300">
          Để lại thông tin — chuyên viên sẽ liên hệ Anh/Chị
        </p>
        <div className="space-y-2">
          <input
            autoFocus
            type="text"
            placeholder="Họ và tên *"
            value={name}
            onChange={e => setName(e.target.value)}
            className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900
                       text-sm px-3 py-2 outline-none focus:ring-2 focus:ring-[#0C3656] focus:border-transparent
                       text-gray-800 dark:text-white placeholder:text-gray-400"
          />
          <input
            type="tel"
            placeholder="Số điện thoại *"
            value={phone}
            onChange={e => setPhone(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            className="w-full rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-900
                       text-sm px-3 py-2 outline-none focus:ring-2 focus:ring-[#0C3656] focus:border-transparent
                       text-gray-800 dark:text-white placeholder:text-gray-400"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setState('ask')}
            className="flex-1 py-2 rounded-lg border border-gray-200 text-xs text-gray-500 hover:bg-gray-50 transition-colors">
            ← Quay lại
          </button>
          <button
            onClick={handleSubmit}
            disabled={!name.trim() || !phone.trim() || loading}
            className="flex-1 py-2 rounded-lg text-white text-xs font-semibold transition-all
                       disabled:opacity-40 hover:opacity-90"
            style={{ backgroundColor: '#2D9E34' }}>
            {loading ? 'Đang gửi...' : 'Xác nhận →'}
          </button>
        </div>
      </div>
    );
  }

  // state === 'ask'
  return (
    <div className="mt-3 pt-2.5 border-t border-gray-100 dark:border-gray-700 space-y-1.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: '#0C3656' }}>
        Anh/Chị muốn
      </p>
      <button
        onClick={() => setState('form')}
        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm
                   border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800
                   hover:border-[#2D9E34] hover:bg-green-50 dark:hover:bg-green-900/10
                   hover:shadow-sm transition-all duration-150 group"
      >
        <span className="shrink-0 w-6 h-6 rounded-full bg-green-100 text-green-700 text-xs
                         flex items-center justify-center font-semibold
                         group-hover:bg-[#2D9E34] group-hover:text-white transition-colors">1</span>
        <span className="flex-1 text-gray-700 dark:text-gray-300 group-hover:text-[#2D9E34] transition-colors">
          ✅ Có, chuyên viên L&C liên hệ tôi trực tiếp
        </span>
        <span className="text-gray-300 group-hover:text-[#2D9E34] transition-colors">→</span>
      </button>
      <button
        onClick={onContinueChat}
        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-left text-sm
                   border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800
                   hover:border-[#0C3656] hover:bg-blue-50 dark:hover:bg-blue-900/20
                   hover:shadow-sm transition-all duration-150 group"
      >
        <span className="shrink-0 w-6 h-6 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-500 text-xs
                         flex items-center justify-center font-semibold
                         group-hover:bg-[#0C3656] group-hover:text-white transition-colors">2</span>
        <span className="flex-1 text-gray-700 dark:text-gray-300 group-hover:text-[#0C3656] transition-colors">
          💬 Không, tiếp tục hỏi chatbot
        </span>
        <span className="text-gray-300 group-hover:text-[#0C3656] transition-colors">→</span>
      </button>
    </div>
  );
}
