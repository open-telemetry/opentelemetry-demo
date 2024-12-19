// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
/**
 * Copied with modification from src/frontend/components/CheckoutForm/CheckoutForm.tsx
 */
import { ThemedScrollView } from "@/components/ThemedScrollView";
import { Field } from "@/components/Field";
import { StyleSheet, Pressable } from "react-native";
import { useForm, Controller } from "react-hook-form";
import { ThemedText } from "@/components/ThemedText";
import { ThemedView } from "@/components/ThemedView";

export interface IFormData {
  email: string;
  streetAddress: string;
  city: string;
  state: string;
  country: string;
  zipCode: string;
  creditCardNumber: string;
  creditCardCvv: number;
  creditCardExpirationYear: number;
  creditCardExpirationMonth: number;
}

interface IProps {
  onSubmit(formData: IFormData): void;
}

const CheckoutForm = ({ onSubmit }: IProps) => {
  const { control, handleSubmit } = useForm({
    defaultValues: {
      email: "someone@example.com",
      streetAddress: "1600 Amphitheatre Parkway",
      city: "Mountain View",
      state: "CA",
      country: "United States",
      zipCode: "94043",
      creditCardNumber: "4432-8015-6152-0454",
      creditCardCvv: 672,
      creditCardExpirationYear: 2030,
      creditCardExpirationMonth: 1,
    },
  });

  return (
    <ThemedScrollView style={styles.container}>
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="E-mail Address"
            placeholder="E-mail Address"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value}
          />
        )}
        name="email"
      />
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="Street Address"
            placeholder="Street Address"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value}
          />
        )}
        name="streetAddress"
      />
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="Zip Code"
            placeholder="Zip Code"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value}
          />
        )}
        name="zipCode"
      />
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="Country"
            placeholder="Country"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value}
          />
        )}
        name="country"
      />
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="Credit Card Number"
            placeholder="Credit Card Number"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value}
            keyboardType="numeric"
          />
        )}
        name="creditCardNumber"
      />
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="Expiration Month"
            placeholder="Month"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value.toString()}
            keyboardType="numeric"
          />
        )}
        name="creditCardExpirationMonth"
      />
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="Expiration Year"
            placeholder="Year"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value.toString()}
            keyboardType="numeric"
          />
        )}
        name="creditCardExpirationYear"
      />
      <Controller
        control={control}
        rules={{ required: true }}
        render={({ field: { onChange, onBlur, value } }) => (
          <Field
            label="CVV"
            placeholder="CVV"
            onBlur={onBlur}
            onChangeText={onChange}
            value={value.toString()}
            keyboardType="numeric"
          />
        )}
        name="creditCardCvv"
      />
      <ThemedView style={styles.submitContainer}>
        <Pressable style={styles.submit} onPress={handleSubmit(onSubmit)}>
          <ThemedText style={styles.submitText}>Place Order</ThemedText>
        </Pressable>
      </ThemedView>
    </ThemedScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    marginLeft: 30,
  },
  submitContainer: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    margin: 20,
  },
  submit: {
    borderRadius: 4,
    backgroundColor: "blue",
    alignItems: "center",
    justifyContent: "center",
    width: 150,
    padding: 10,
    position: "relative",
  },
  submitText: {
    color: "white",
    fontSize: 20,
  },
});

export default CheckoutForm;
