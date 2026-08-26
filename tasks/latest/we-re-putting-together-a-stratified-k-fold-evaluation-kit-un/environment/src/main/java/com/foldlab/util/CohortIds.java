package com.foldlab.util;

import java.math.BigInteger;
import java.util.Comparator;
import java.util.function.Function;

/** Arbitrary-precision numeric ordering for cohort row identifiers. */
public final class CohortIds {
    private CohortIds() {}

    public static BigInteger parse(String id) {
        if (id == null) {
            throw new IllegalArgumentException("id is required");
        }
        String trimmed = id.trim();
        if (trimmed.isEmpty()) {
            throw new IllegalArgumentException("id is blank");
        }
        return new BigInteger(trimmed);
    }

    public static final Comparator<String> ORDER = Comparator.comparing(CohortIds::parse);

    public static <T> Comparator<T> comparing(Function<? super T, String> idGetter) {
        return Comparator.comparing(idGetter, ORDER);
    }
}
