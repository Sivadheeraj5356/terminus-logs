package rlog;

import java.nio.charset.StandardCharsets;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public final class AuthCode {
    private AuthCode() {
    }

    public static String canonical(Message m) {
        StringBuilder sb = new StringBuilder();
        sb.append(m.kind).append('|');
        sb.append(m.view).append('|');
        sb.append(m.opnum).append('|');
        sb.append(m.op).append('|');
        sb.append(m.commitNum).append('|');
        sb.append(m.from).append('|');
        for (int i = 0; i < m.log.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(m.log[i]);
        }
        sb.append('|');
        for (int i = 0; i < m.aux.length; i++) {
            if (i > 0) {
                sb.append(',');
            }
            sb.append(m.aux[i]);
        }
        return sb.toString();
    }

    public static String compute(byte[] secret, String canonical) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret, "HmacSHA256"));
            byte[] raw = mac.doFinal(canonical.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(raw.length * 2);
            for (byte b : raw) {
                hex.append(Character.forDigit((b >> 4) & 0xF, 16));
                hex.append(Character.forDigit(b & 0xF, 16));
            }
            return hex.toString();
        } catch (java.security.GeneralSecurityException e) {
            throw new IllegalStateException(e);
        }
    }
}
