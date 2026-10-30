# Synthetic example only — Order tracking mini-service

> This business brief is fictitious sample content for demonstrating ForgeSDLC. It does not describe a real customer, company or production system.

The system shall allow a signed-in customer to view the current status of an order by entering an order number.

The system must display the last status update time alongside the current order status.

The system shall reject an order lookup when the order number does not belong to the signed-in customer.

The system should allow a customer to download the tracking history as a CSV file.

The service should remain available during normal weekday business hours. The source does not define a measurable availability target; clarify the target with the product owner rather than inventing one.

The system shall record an audit event when a customer views an order tracking history.
