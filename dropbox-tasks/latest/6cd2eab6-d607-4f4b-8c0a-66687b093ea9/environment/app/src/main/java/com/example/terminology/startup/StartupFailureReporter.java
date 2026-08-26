
package com.example.terminology.startup;
import com.example.terminology.api.ErrorResponse;
import java.util.Map;
public class StartupFailureReporter {
  public static ErrorResponse format(String code, String message) {
    return new ErrorResponse(new ErrorResponse.ErrorBody(code, message, Map.of()));
  }
}
